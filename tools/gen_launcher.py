# -*- coding: utf-8 -*-
"""生成双击启动的 .vbs（UTF-16 带 BOM，WSH 才能正确解析中文路径）。

用法：python tools/gen_launcher.py
产物：项目根目录下的 启动看板.vbs
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "run_sidebar.py"      # 走守护进程：能热重载、能崩了自愈

# 优先用 pythonw.exe，避免黑窗口；找不到就退回 python.exe
py = Path(sys.executable)
if py.name.lower() == "python.exe" and (py.with_name("pythonw.exe")).exists():
    py = py.with_name("pythonw.exe")

content = """Set sh = CreateObject("WScript.Shell")
q = Chr(34)
py = "{py}"
sc = "{sc}"
sh.CurrentDirectory = "{base}"
sh.Run q & py & q & " " & q & sc & q, 0, False
""".format(py=str(py), sc=str(TARGET), base=str(ROOT))

out = ROOT / "启动看板.vbs"
out.write_text(content, encoding="utf-16")
print("written:", out)
print("python :", py)
