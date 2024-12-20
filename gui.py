# build
# pyinstaller --onefile --name 微信群聊监控 --windowed --distpath ./ ./gui.py

import tkinter as tk
from tkinter import scrolledtext
import threading,subprocess
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# 创建主窗口
root = tk.Tk()
root.title("微信群聊监控工具")
root.geometry("800x600")

# 创建一个滚动文本框，用于显示实时输出
output_box = scrolledtext.ScrolledText(root, width=70, height=20, wrap=tk.WORD)
output_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)  # 自适应窗口大小

output_box.insert(tk.END,f'''
    使用说明：\n
    1、先登录微信（最好是老号避免腾讯风控，微信必须是3.9.10.27版本且关闭更新）\n
    2、然后点击运行启动按钮，注意看是否有被杀软拦截，如有请关闭杀软\n
    3、运行起来后，把它拉入要监控的企微群即可\n\n
    tips：\n
    1、监控群聊指令：请亿速云客服重点关注一下本群xxx（xxx填写群名称，任何人发送均可，每个群都要发）\n
    2、标记内部人员指令：#1 亿速云xxx（xxx填写内部人员名称，需内部人员自己发送，一个群发了其它群共享）\n
    3、默认情况下所有企业微信联系人都认为是内部人员，可以不用标记内部人员，但是监控群聊指令必须要发的\n
''')
output_box.yview(tk.END)
root.update()

python_process = None
stdout_thread = None
stderr_thread = None

def read_output(pipe):
    info = ""
    for line in iter(pipe.readline, b''):  # 使用 iter 来读取直到 EOF
        if isinstance(line, bytes):  # 如果是字节串
            info = line.decode('gbk', errors='ignore')
        else:  # 如果已经是字符串
            info = line
        line_count = int(output_box.index('end-1c').split('.')[0])
        if line_count > 40:
            output_box.delete(1.0, tk.END)
        output_box.insert(tk.END, info)
        output_box.yview(tk.END)
        root.update()
    pipe.close()

# 创建按钮的回调函数，用于调用另一个Python脚本
def run_script():
    global python_process,stdout_thread,stderr_thread
    try:
        run_button.config(state=tk.DISABLED)
        # 启动子进程，运行另一个Python脚本，设置为实时输出
        python_process = subprocess.Popen(
            './python-3.11.8-embed-amd64/python.exe ./start.py',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # 以文本模式打开（支持中文）
            bufsize=1,  # 设置为行缓冲
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        stdout_thread = threading.Thread(target=read_output, args=(python_process.stdout, ), daemon=True).start()
        stderr_thread = threading.Thread(target=read_output, args=(python_process.stderr, ), daemon=True).start()
    except Exception as e:
        output_box.insert(tk.END, f"发生错误：{str(e)}\n")
        output_box.yview(tk.END)
        root.update()

# 创建按钮
run_button = tk.Button(root, text="先登录好微信然后点击此处运行启动", command=run_script)
run_button.pack(pady=10)

# 最小化窗口并隐藏
def minimize_window():
    root.withdraw()  # 隐藏窗口

# 创建托盘图标
def create_tray_icon():
    # 创建图标
    image = Image.new('RGB', (64, 64), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 64, 64), fill=(0, 0, 0))
    draw.text((10, 10), "App", fill=(255, 255, 255))

    # 设置菜单
    menu = (item('恢复', restore_window), item('退出', exit_application))
    
    # 创建托盘图标
    icon = pystray.Icon("test_icon", image, "托盘图标", menu)
    icon.run()

# 恢复窗口
def restore_window(icon, item):
    root.deiconify()  # 恢复窗口显示
    icon.stop()  # 停止托盘图标

# 退出应用
def exit_application(icon, item):
    global python_process,stdout_thread,stderr_thread
    if python_process is not None:
        python_process.terminate()
    if icon is not None:
        icon.stop()  # 停止托盘图标
    root.quit()  # 退出应用

def on_close():
    exit_application(None, None)

# 创建最小化按钮的回调函数
def on_minimize():
    minimize_window()
    create_tray_icon()

# 创建最小化按钮
# minimize_button = tk.Button(root, text="持续运行并隐藏至任务栏", command=on_minimize)
# minimize_button.pack(pady=5)

# 启动GUI主循环
root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()