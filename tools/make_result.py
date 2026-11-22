# -*- coding: utf-8 -*-
"""给「任何 AI / 任何脚本」用的验收写回工具。

用法：
    python tools/make_result.py --queue                 # 列出待验收的提交
    python tools/make_result.py <id> pass               # 判定通过
    python tools/make_result.py <id> fail "没看到代码"   # 判定不通过，附原因

写回后看板 1.2 秒内自动应用。这个脚本只是替你把 JSON 写对，
验收方是谁都行：脚本、别的 AI 会话、甚至手写。
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
QUEUE = BASE / "verify-queue.jsonl"
RESULTS = BASE / "verify-result.jsonl"


def read_lines(p):
    try:
        return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def show_queue():
    rows = read_lines(QUEUE)
    if not rows:
        print("队列是空的：还没有人提交。")
        return
    done = {json.loads(r).get("id") for r in read_lines(RESULTS) if r.strip().startswith("{")}
    for i, line in enumerate(rows, 1):
        try:
            d = json.loads(line)
        except Exception:
            print("[%d] 无法解析：%s" % (i, line))
            continue
        flag = "已验收" if d.get("id") in done else "待验收"
        print("[%d] %-4s id=%s\n    %s\n    成果目录：%s" % (
            i, flag, d.get("id"), d.get("text", ""), d.get("dir", "")))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] in ("--queue", "-q"):
        show_queue()
        return 0
    if len(args) < 2:
        print("缺参数。用法：make_result.py <id> pass|fail [原因]")
        return 2
    iid, verdict = args[0], args[1].lower()
    reason = args[2] if len(args) > 2 else ""
    if verdict not in ("pass", "fail"):
        print("verdict 只能是 pass 或 fail")
        return 2
    rec = {"id": iid, "verdict": verdict, "reason": reason, "ts": time.time()}
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("已写入：", json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
