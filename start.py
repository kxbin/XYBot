import os,sys
sys.path.append(os.getcwd())
import shutil,socket,pynng,schedule,yaml
from loguru import logger
from wcferry import wcf_pb2, WxMsg

import utils.xybot as xybot
from utils.plans_manager import plan_manager
from utils.plugin_manager import plugin_manager
from wcferry_helper import *


async def recv_msg_async(sock, rsp):
    loop = asyncio.get_running_loop()
    try:
        message = await loop.run_in_executor(None, sock.recv_msg, True)
        rsp.ParseFromString(message.bytes)
    except Exception as e:
        raise Exception(f"接受消息失败:{e}")
    return rsp.wxmsg


def callback(worker):  # 处理线程结束时，有无错误
    worker_exception = worker.exception()
    if worker_exception:
        logger.error(worker_exception)


async def plan_run_pending():  # 计划等待判定线程
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)


def is_port_in_use(ip: str, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((ip, port)) == 0


async def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists('audio/temp'):
        shutil.rmtree('audio/temp')
    os.makedirs('audio/temp')

    # ---- log设置 读取设置 ---- #
    logger.add(
        "logs/log_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8",
        enqueue=True,
        retention="2 weeks",
        rotation="00:01",
    )  # 日志设置
    logger.info("已设置日志")

    cache_path = "resources/cache"  # 检测是否有cache文件夹
    if not os.path.exists(cache_path):
        logger.info("检测到未创建cache缓存文件夹")
        os.makedirs(cache_path)
        logger.info("已创建cache文件夹")

    with open("main_config.yml", "r", encoding="utf-8") as f:  # 读取设置
        config = yaml.safe_load(f.read())

    ip = config["ip"]
    port = config["port"]

    logger.info("读取设置成功")

    # ---- 微信Hook注入 修复微信版本过低问题 机器人实例化 登陆监测 机器人启动 ---- #

    # 注入
    if ip == "127.0.0.1" or ip == "localhost":
        if not is_port_in_use(ip, port):
            logger.info("开始注入Wcferry")
            inject(port, debug=True, local=True)
            if is_port_in_use(ip, port):
                logger.success("Wcferry注入成功")
            else:
                logger.error("Wcferry注入失败")
                return

        else:
            logger.success("Wcferry已被注入")
    else:
        logger.success("检测到远程调试，无需注入")

    # 实例化
    logger.debug(f"IP: {ip}, 端口: {port}")
    bot = client.Wcf(ip, port, debug=False, block=False)
    logger.info("机器人实例化成功")

    # 检查是否登陆了微信
    logger.info("开始检测微信是否登陆")
    if not bot.is_login():
        logger.warning("机器人微信账号未登录！请扫码登陆微信。")
        while not bot.is_login():
            await asyncio.sleep(1)

    logger.debug(f"微信账号: {bot.get_self_wxid()}")

    logger.success("已确认微信已登陆，开始启动XYBot")
    handlebot = xybot.XYBot(bot)

    # ---- 加载插件 加载计划 ---- #

    # 加载所有插件
    plugin_manager.load_plugins()  # 加载所有插件
    logger.success("已加载所有插件")

    plans_dir = "plans"
    plan_manager.load_plans(bot, plans_dir)  # 加载所有计划

    asyncio.create_task(plan_run_pending()).add_done_callback(callback)  # 开启计划等待判定线程
    logger.success("已加载所有计划，并开始后台运行")

    logger.debug(bot.get_msg_types())

    # ---- 开始接受处理消息 ---- #
    req = wcf_pb2.Request()
    req.func = wcf_pb2.FUNC_ENABLE_RECV_TXT
    bot._send_request(req)

    await asyncio.sleep(5) # 等待微信消息接受准备

    rsp = wcf_pb2.Response()

    with pynng.Pair1() as sock:
        sock.dial(bot.msg_url, block=True)
        logger.success(f"连接成功: {bot.msg_url}")

        logger.info("开始接受消息")
        while True:
            message = await recv_msg_async(sock, rsp)
            asyncio.create_task(handlebot.message_handler(bot, WxMsg(message))).add_done_callback(callback)


if __name__ == "__main__":
    asyncio.run(main())
