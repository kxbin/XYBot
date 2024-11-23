#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.

import os,re,yaml,time,json,queue,uuid,threading
from loguru import logger
from openai import AsyncOpenAI
from wcferry import client

from utils.database import BotDatabase
from utils.plugin_interface import PluginInterface
from wcferry_helper import XYBotWxMsg

from playsound import playsound
from utils.coze import ck_exec_thread, coze_client, get_audio

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

        self.wait_second = config["wait_second"] # 用户提问，等待多少秒才播报

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

        # 自定义
        self.group_latest_msg = {}
        self.group_reply_time = {}
        with open('white_group.json', 'r', encoding='utf-8') as f:
            self.white_group = json.load(f)
        with open('white_people.json', 'r', encoding='utf-8') as f:
            self.white_people = json.load(f)
        self.notify_queue = queue.Queue()
        threading.Thread(target=self.notify, daemon=True).start()

    def notify(self):
        while True:
            try:
                item = self.notify_queue.get()
                second = item['second']
                roomid = item['roomid']
                msg = item['msg']
                roomname = self.white_group[roomid]

                # ---开始插入ck
                data = [
                    (str(roomid), roomname, str(msg)),
                ]
                ck_exec_thread('INSERT INTO notify_log (roomid, roomname, msg) VALUES', data)
                # ---结束插入ck

                text1 = "群名：{}".format(roomname[:20])
                text2 = "问题是：{}".format(msg[:20])
                file1 = 'audio/temp/{}.wav'.format(str(uuid.uuid4()))
                file2 = 'audio/temp/{}.wav'.format(str(uuid.uuid4()))
                status1 = get_audio(file1, text1)
                status2 = get_audio(file2, text2)

                playsound('audio/0.mp3')
                playsound('audio/5.wav')
                if status1:
                    playsound(file1)
                if status2:
                    playsound(file2)
            except queue.Empty:
                time.sleep(1)

    def group_process(self, bot: client.Wcf, roomid, sender, msg):
        self.group_latest_msg[roomid] = msg
        if sender in self.white_people:
            self.group_reply_time[roomid] = time.time()
        
        # 每秒检查持续5分钟，如5分钟内有公司自己人回复或有最新提问，则结束此线程，否则AI回复
        now = time.time()
        end = now + self.wait_second
        while now < end:
            time.sleep(1)
            now = time.time()
            if roomid in self.group_reply_time and now < (self.group_reply_time[roomid] + 300):
                return
            if self.group_latest_msg[roomid] != msg:
                return
        
        self.notify_queue.put({
            'second': self.wait_second,
            'roomid': roomid,
            'msg': msg
        })
        bot.send_text("请您稍等，我们人员正在跟进中", roomid)

        # 每5分钟检查持续6分钟，如还没有自己人回复，则持续广播
        # now = time.time()
        # end = now + 360
        # while now < end:
        #     self.notify_queue.put({
        #         'minute': 11-int((end-now)/60),
        #         'roomid': roomid,
        #         'msg': msg
        #     })
        #     time.sleep(300)
        #     now = time.time()
        #     if roomid in self.group_reply_time and now < (self.group_reply_time[roomid] + 310):
        #         return

    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        msg = re.sub(r'@.*?\u2005', '', recv.content)

        if msg.startswith("我是"):
            return  # 微信打招呼消息，不需要处理
        elif recv.from_group():
            if "请亿速云客服重点关注一下本群" in msg:
                self.white_group[recv.roomid] = msg.replace("请亿速云客服重点关注一下本群", "")
                with open('white_group.json', 'w', encoding='utf-8') as f:
                    json.dump(self.white_group, f, ensure_ascii=False, indent=4)
                bot.send_text("收到，我会的", recv.roomid)
                return  # 如果是群里加白指令
            elif "大家好，我是亿速云" in msg or (match := re.search(r"^#\d+ 亿速云", msg)):
                self.white_people[recv.sender] = msg.replace("大家好，我是亿速云", "")
                self.white_people[recv.sender] = msg.replace(match.group(), "")
                with open('white_people.json', 'w', encoding='utf-8') as f:
                    json.dump(self.white_people, f, ensure_ascii=False, indent=4)
                bot.send_text(self.white_people[recv.sender] + "[鼓掌]", recv.roomid)
                return  # 如果是人员加白指令
            elif recv.roomid not in self.white_group:
                return  # 如果消息不来自加白的群，不处理
            
            # ---开始插入ck
            is_white_people = 0
            sendername = ''
            roomname = self.white_group[recv.roomid]
            if recv.sender in self.white_people:
                is_white_people = 1
                sendername = self.white_people[recv.sender]
            data = [
                (is_white_people, str(recv.sender), sendername, str(recv.roomid), roomname, str(recv.content)),
            ]
            ck_exec_thread('INSERT INTO wechat_log (is_white_people, sender, sendername, roomid, roomname, content) VALUES', data)
            # ---结束插入ck

            threading.Thread(target=self.group_process, args=(bot, recv.roomid, recv.sender, msg, ), daemon=True).start()

        # wxid = recv.sender
        # chat_poll = coze_client.chat.create_and_poll(
        #     bot_id='7418104570632732722',
        #     user_id='test',
        #     additional_messages=[Message.build_user_question_text(msg)]
        # )
        # if chat_poll.chat.status == ChatStatus.COMPLETED:
        #     bot.send_text(chat_poll.messages[0].content, recv.roomid)
        #     logger.info(f'[发送信息]{chat_poll.messages[0].content}| [发送到] {wxid}')

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
