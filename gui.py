import tkinter as tk
from tkinter import scrolledtext
import subprocess
import sys

# 创建主窗口
root = tk.Tk()
root.title("运行Python脚本并实时显示输出")
root.geometry("600x400")

# 创建一个滚动文本框，用于显示实时输出
output_box = scrolledtext.ScrolledText(root, width=70, height=20, wrap=tk.WORD)
output_box.pack(padx=10, pady=10)

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

# 启动GUI主循环
root.mainloop()