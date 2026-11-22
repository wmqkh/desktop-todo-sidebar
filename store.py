# -*- coding: utf-8 -*-
"""数据读写与默认配置。"""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
TASKS = BASE / "tasks.json"
TASKS_EXAMPLE = BASE / "tasks.example.json"
UI = BASE / "ui.json"
STATE = BASE / "state.json"
QUEUE = BASE / "verify-queue.jsonl"
RESULTS = BASE / "verify-result.jsonl"
OUTDIR = BASE / "成果"

VERSION = "0.2.0"

DEFAULT_UI = {
    "dayIndex": 0,
    "width": 340,
    "height": 0,          # 0 = 自动（屏高 - 60）
    "alpha": 0.66,
    "font_size": 10,
    "bg_color": "#000000",
    "fg_mode": "light",   # light = 深底浅字，dark = 浅底深字
}

# 预设背景色
PRESETS = [
    ("#000000", "纯黑"),
    ("#12161c", "深墨"),
    ("#1b1b1b", "炭灰"),
    ("#12251e", "墨绿"),
    ("#20180f", "胡桃"),
    ("#0e1a24", "藏蓝"),
    ("#2e2e2e", "石墨"),
    ("#f2f2f2", "浅底"),
]

LIMITS = dict(width=(240, 900), height=(240, 2000), alpha=(0.30, 1.0),
              font=(8, 16), size_step=1)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    p = Path(path)
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def read_lines(path):
    try:
        return [l for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def load_tasks():
    """优先 tasks.json；没有就用 tasks.example.json，方便别人 clone 后直接跑。"""
    for p in (TASKS, TASKS_EXAMPLE):
        data = load(p, None)
        if isinstance(data, dict):
            return data
    return {"meta": {}, "week": [], "days": []}


def fg_colors(mode):
    """返回 (正文, 次要, 更弱) 三档文字色。"""
    if mode == "dark":
        return "#1c1c1c", "#5f5f5f", "#8a8a8a"
    return "#f2f2f2", "#a0a0a0", "#6e6e6e"


def clamp(v, key):
    lo, hi = LIMITS[key]
    return max(lo, min(hi, v))
