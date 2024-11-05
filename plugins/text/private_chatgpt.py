#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.

import re,yaml,json
from loguru import logger
from openai import AsyncOpenAI
from wcferry import client

from utils.database import BotDatabase
from utils.plugin_interface import PluginInterface
from wcferry_helper import XYBotWxMsg

from cozepy import Message, ChatStatus
from utils.coze import coze_client
white_group = []
with open('white_group.json', 'r') as f:
    white_group = json.load(f)
    print(white_group)

class private_chatgpt(PluginInterface):
    def __init__(self):
        config_path = "plugins/text/private_chatgpt.yml"

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f.read())

        self.enable_private_chat_gpt = config["enable_private_chat_gpt"]  # 是否开启私聊chatgpt

        self.gpt_version = config["gpt_version"]  # gpt版本
        self.gpt_max_token = config["gpt_max_token"]  # gpt 最大token
        self.gpt_temperature = config["gpt_temperature"]  # gpt 温度

        self.private_chat_gpt_price = config["private_chat_gpt_price"]  # 私聊gpt使用价格（单次）
        self.dialogue_count = config["dialogue_count"]  # 保存的对话轮数
        self.clear_dialogue_keyword = config["clear_dialogue_keyword"]

        main_config_path = "main_config.yml"
        with open(main_config_path, "r", encoding="utf-8") as f:  # 读取设置
            main_config = yaml.safe_load(f.read())

        self.admins = main_config["admins"]  # 管理员列表

        self.openai_api_base = main_config["openai_api_base"]  # openai api 链接
        self.openai_api_key = main_config["openai_api_key"]  # openai api 密钥

        sensitive_words_path = "sensitive_words.yml"  # 加载敏感词yml
        with open(sensitive_words_path, "r", encoding="utf-8") as f:  # 读取设置
            sensitive_words_config = yaml.safe_load(f.read())
        self.sensitive_words = sensitive_words_config["sensitive_words"]  # 敏感词列表

        self.db = BotDatabase()

    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        recv.content = re.split(" |\u2005", recv.content) # 拆分消息
        # 这里recv.content中的内容是分割的
        msg = " ".join(recv.content)

        if not self.enable_private_chat_gpt:
            return  # 如果不开启私聊chatgpt，不处理
        elif msg.startswith("我是"):
            return  # 微信打招呼消息，不需要处理
        elif msg == "请将此群加入AI回复白名单":
            white_group.append(recv.roomid)
            with open('white_group.json', 'w') as f:
                json.dump(white_group, f)
            bot.send_text("收到，已将此群加入AI回复白名单" + recv.roomid, recv.roomid)
            return  # 如果是群里加白指令
        elif recv.from_group() and (recv.roomid not in white_group):
            return  # 如果消息不来自加白的群，不处理

        wxid = recv.sender
        chat_poll = coze_client.chat.create_and_poll(
            bot_id='7418104570632732722',
            user_id='test',
            additional_messages=[Message.build_user_question_text(msg)]
        )
        if chat_poll.chat.status == ChatStatus.COMPLETED:
            bot.send_text(chat_poll.messages[0].content, recv.roomid)
            logger.info(f'[发送信息]{chat_poll.messages[0].content}| [发送到] {wxid}')

    async def chatgpt(self, wxid: str, message: str):  # 这个函数请求了openai的api
        request_content = self.compose_gpt_dialogue_request_content(wxid, message)  # 构成对话请求内容，返回一个包含之前对话的列表

        client = AsyncOpenAI(api_key=self.openai_api_key, base_url=self.openai_api_base)
        try:
            chat_completion = await client.chat.completions.create(
                messages=request_content,
                model=self.gpt_version,
                temperature=self.gpt_temperature,
                max_tokens=self.gpt_max_token,
            )  # 调用openai api

            self.save_gpt_dialogue_request_content(wxid, request_content,
                                                   chat_completion.choices[0].message.content)  # 保存对话请求与回答内容
            return True, chat_completion.choices[0].message.content  # 返回对话回答内容
        except Exception as error:
            return False, error

    def compose_gpt_dialogue_request_content(self, wxid: str, new_message: str) -> list:
        json_data = self.db.get_private_gpt_data(wxid)  # 从数据库获得到之前的对话

        if not json_data or "data" not in json_data.keys():  # 如果没有对话数据，则初始化
            init_data = {"data": []}
            json_data = init_data

        previous_dialogue = json_data['data'][self.dialogue_count * -2:]  # 获取指定轮数的对话，乘-2是因为一轮对话包含了1个请求和1个答复
        request_content = [{"role": "system", "content": "You are a helpful assistant that speaks in plain text."}]
        request_content += previous_dialogue  # 将之前的对话加入到api请求内容中

        request_content.append({"role": "user", "content": new_message})  # 将用户新的问题加入api请求内容

        return request_content

    def save_gpt_dialogue_request_content(self, wxid: str, request_content: list, gpt_response: str) -> None:
        request_content.append({"role": "assistant", "content": gpt_response})  # 将gpt回答加入到api请求内容
        request_content = request_content[self.dialogue_count * -2:]  # 将列表切片以符合指定的对话轮数，乘-2是因为一轮对话包含了1个请求和1个答复

        json_data = {"data": request_content}  # 构成保存需要的json数据
        self.db.save_private_gpt_data(wxid, json_data)  # 保存到数据库中

    def senstitive_word_check(self, message):  # 检查敏感词
        for word in self.sensitive_words:
            if word in message:
                return False
        return True

    def clear_dialogue(self, wxid):  # 清除对话记录
        self.db.save_private_gpt_data(wxid, {"data": []})
