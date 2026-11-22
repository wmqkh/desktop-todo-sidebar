# -*- coding: utf-8 -*-
"""看板守护进程：负责启动 / 自动重启 / 崩溃拉起。

为什么需要它：程序自己重启自己（Popen + 退出）在 Windows 上不够可靠，
对外层循环来说这就只是"子进程退出了，再起一个"。

退出码约定：
    0  = 用户主动关闭，守护进程也退出
    42 = 请求重启（源码变更），立即重新拉起
    其他 = 崩溃，等 2 秒后拉起（连续崩溃会被拉开间隔）
"""
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP = BASE / "sidebar.py"
RELOAD_CODE = 42


def main():
    crashes = 0
    while True:
        started = time.time()
        try:
            rc = subprocess.run([sys.executable, str(APP)], cwd=str(BASE)).returncode
        except KeyboardInterrupt:
            return 0

        if rc == 0:
            return 0
        if rc == RELOAD_CODE:
            crashes = 0
            time.sleep(0.4)
            continue

        # 崩溃：跑得越短说明越可能是启动失败，退避避免疯狂重启
        crashes = crashes + 1 if (time.time() - started) < 5 else 1
        time.sleep(min(2 * crashes, 20))


if __name__ == "__main__":
    sys.exit(main())
