# -*- coding: utf-8 -*-
"""最简"验收方"示例：盯住 verify-queue.jsonl，一旦有新提交就打印并退出。

这里只是一个骨架——任何程序（脚本 / 服务 / AI 助手）都可以：
  1. 读 verify-queue.jsonl 拿到待验收的 id 和成果目录
  2. 核对成果
  3. 往 verify-result.jsonl 追加 {"id","verdict":"pass|fail","reason"}
本脚本只做第 1 步，用来演示怎么"守着"队列。"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent   # 上一层就是项目根
QUEUE = BASE / "verify-queue.jsonl"


def lines():
    try:
        return [l for l in QUEUE.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


start = len(lines())
print("[watch] baseline=%d 开始等待提交…" % start, flush=True)
while True:
    time.sleep(2)
    cur = lines()
    if len(cur) > start:
        print("[watch] 收到 %d 条新提交：" % (len(cur) - start), flush=True)
        for l in cur[start:]:
            try:
                d = json.loads(l)
                print("  - %s | %s | %s" % (d.get("id"), d.get("text"), d.get("dir")), flush=True)
            except Exception:
                print("  - " + l, flush=True)
        sys.exit(0)
