import tkinter as tk
from tkinter import scrolledtext
import subprocess
import sys
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# 创建主窗口
root = tk.Tk()
root.title("微信群聊监控工具，先登录微信，再点击运行按钮")
root.geometry("600x400")

# 创建一个滚动文本框，用于显示实时输出
output_box = scrolledtext.ScrolledText(root, width=70, height=20, wrap=tk.WORD)
output_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)  # 自适应窗口大小

# 创建按钮的回调函数，用于调用另一个Python脚本
def run_script():
    try:
        # 启动子进程，运行另一个Python脚本，设置为实时输出
        process = subprocess.Popen(
            ['python', 'start.py'],  # 替换为你需要运行的脚本路径
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # 以文本模式打开（支持中文）
            bufsize=1,  # 设置为行缓冲
            encoding='utf-8'  # 确保输出是utf-8编码的
        )
        
        # 实时读取输出并更新文本框
        for line in process.stdout:
            output_box.insert(tk.END, line)  # 将输出追加到文本框
            output_box.yview(tk.END)  # 自动滚动到文本框底部
            root.update()  # 更新GUI界面以实时显示输出
        
        # 读取并显示错误信息（如果有的话）
        err = process.stderr.read()
        if err:
            output_box.insert(tk.END, f"错误：{err}\n")
            output_box.yview(tk.END)
            root.update()

        # 等待子进程结束
        process.wait()
    except Exception as e:
        output_box.insert(tk.END, f"发生错误：{str(e)}\n")
        output_box.yview(tk.END)
        root.update()

# 创建按钮
run_button = tk.Button(root, text="运行脚本", command=run_script)
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
    root.quit()  # 退出应用
    icon.stop()  # 停止托盘图标

# 创建最小化按钮的回调函数
def on_minimize():
    minimize_window()
    create_tray_icon()

# 创建最小化按钮
minimize_button = tk.Button(root, text="持续运行并隐藏至任务栏", command=on_minimize)
minimize_button.pack(pady=5)

# 启动GUI主循环
root.mainloop()