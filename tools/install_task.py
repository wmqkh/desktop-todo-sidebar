# -*- coding: utf-8 -*-
"""把 auto_verify.py 注册成 Windows 计划任务。

用法：
    python tools/install_task.py              # 安装/覆盖，每 5 分钟
    python tools/install_task.py --minutes 2  # 改频率
    python tools/install_task.py --remove     # 卸载

不弹黑框的做法：直接调用 pythonw.exe（GUI 子系统，不分配控制台），
不经过 .bat —— 批处理必须由 cmd.exe 执行，那才会闪窗口。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = "TodoSidebarAutoVerify"
SCRIPT = ROOT / "auto_verify.py"


def find_pythonw():
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return cand if cand.exists() else exe


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    if args.remove:
        rc, out = run(["schtasks", "/delete", "/tn", TASK, "/f"])
        print(out or ("已删除" if rc == 0 else "删除失败"))
        return rc

    pyw = find_pythonw()
    cmd = '"%s" "%s" --quiet' % (pyw, SCRIPT)
    print("任务命令:", cmd)

    rc, out = run([
        "schtasks", "/create", "/f", "/sc", "minute", "/mo", str(args.minutes),
        "/tn", TASK, "/tr", cmd,
    ])
    print(out)
    if rc != 0:
        print("\n安装失败。可以先手动确认脚本本身能跑：")
        print('  "%s" "%s" --dry' % (pyw, SCRIPT))
        return rc

    # 老版本遗留的批处理启动器，删掉免得误用
    old = ROOT / "tools" / "run_auto_verify.bat"
    if old.exists():
        old.unlink()
        print("已删除旧启动器:", old.name)

    print("\n已安装：每 %d 分钟静默跑一次（pythonw，无黑框）" % args.minutes)
    print("查看: schtasks /query /tn %s" % TASK)
    print("卸载: python tools/install_task.py --remove")
    return 0


if __name__ == "__main__":
    sys.exit(main())
