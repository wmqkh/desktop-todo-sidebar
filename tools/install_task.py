# -*- coding: utf-8 -*-
"""把 auto_verify.py 注册成 Windows 计划任务（每 5 分钟跑一次）。

用法（在本目录执行）：

    python tools/install_task.py            # 安装/覆盖，每 5 分钟
    python tools/install_task.py --minutes 2
    python tools/install_task.py --remove   # 卸载

为什么要它：DSH 关掉之后 AI 不会主动出现，但"成果目录里有没有东西、链接真不真、
commit 够不够"这类硬性检查不需要 AI——交给系统定时跑就行。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = "TodoSidebarAutoVerify"
BAT = ROOT / "tools" / "run_auto_verify.bat"


def find_pythonw():
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return cand if cand.exists() else exe


def write_bat():
    py = find_pythonw()
    BAT.write_text(
        '@echo off\r\n'
        'chcp 65001 >nul\r\n'
        '"%s" "%s" --quiet\r\n' % (py, ROOT / "auto_verify.py"),
        encoding="utf-8",
    )
    return BAT


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    if args.remove:
        rc, out = run(["schtasks", "/delete", "/tn", TASK, "/f"])
        print(out.strip() or ("已删除" if rc == 0 else "删除失败"))
        return rc

    bat = write_bat()
    print("启动脚本:", bat)
    rc, out = run([
        "schtasks", "/create", "/f", "/sc", "minute", "/mo", str(args.minutes),
        "/tn", TASK, "/tr", str(bat),
    ])
    print(out.strip())
    if rc != 0:
        print("\n安装失败。可以先跑一次看看逻辑：")
        print('  "%s" "%s" --dry' % (find_pythonw(), ROOT / "auto_verify.py"))
        return rc
    print("\n已安装：每 %d 分钟自动核验一次（DSH 关着也会跑）" % args.minutes)
    print("查看: schtasks /query /tn %s" % TASK)
    print("卸载: python tools/install_task.py --remove")
    return 0


if __name__ == "__main__":
    sys.exit(main())
