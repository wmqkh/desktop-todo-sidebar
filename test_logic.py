# -*- coding: utf-8 -*-
"""看板逻辑回归测试：下一天放行条件 + 验收回写。不污染真实数据。"""
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = HERE / ".test_tmp"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)
shutil.copyfile(HERE / "tasks.example.json", TMP / "tasks.json")
(TMP / "ui.json").write_text(json.dumps({"dayIndex": 0, "width": 340, "alpha": 0.66}), encoding="utf-8")
(TMP / "state.json").write_text(json.dumps({"items": {}, "appliedResults": 0}), encoding="utf-8")
(TMP / "verify-result.jsonl").write_text("", encoding="utf-8")

sys.path.insert(0, str(HERE))
import store as st  # noqa: E402

st.TASKS = TMP / "tasks.json"
st.TASKS_EXAMPLE = TMP / "tasks.json"
st.UI = TMP / "ui.json"
st.STATE = TMP / "state.json"
st.QUEUE = TMP / "verify-queue.jsonl"
st.RESULTS = TMP / "verify-result.jsonl"
st.OUTDIR = TMP / "成果"

spec = importlib.util.spec_from_file_location("sidebar_under_test", HERE / "sidebar.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

import tkinter as tk  # noqa: E402

root = tk.Tk()
app = m.App(root)
ok = True


def check(name, cond, detail=""):
    global ok
    ok = ok and cond
    print("%-34s %s %s" % (name, "PASS" if cond else "FAIL", detail))


# 1 没勾完不许进下一天
app.change_day(1)
check("未勾选时不许进下一天", app.day_index() == 0, "dayIndex=%d" % app.day_index())

# 2 全部提交后放行
for it in app.cur_day()["items"]:
    app.state["items"][it["id"]] = {"status": "pending", "ts": 0, "reason": ""}
app.render()
app.change_day(1)
check("全部提交后允许进下一天", app.day_index() == 1, "dayIndex=%d" % app.day_index())

# 3 最后一天被挡住
app.ui["dayIndex"] = len(app.days()) - 1
for it in app.cur_day()["items"]:
    app.state["items"][it["id"]] = {"status": "ok", "ts": 0, "reason": ""}
app.render()
last = len(app.days()) - 1
app.change_day(1)
check("最后一天再点被挡住", app.day_index() == last, "dayIndex=%d" % app.day_index())

# 4 验收不通过 -> 去勾 + 原因
app.ui["dayIndex"] = 0
first = app.cur_day()["items"][0]["id"]
app.state["items"][first] = {"status": "pending", "ts": 0, "reason": ""}
app.state["appliedResults"] = 0
(TMP / "verify-result.jsonl").write_text(
    json.dumps({"id": first, "verdict": "fail", "reason": "没有看到文件"}, ensure_ascii=False) + "\n",
    encoding="utf-8")
app.apply_results()
s1 = app.state["items"][first]
check("不通过自动去勾", s1["status"] == "todo" and "文件" in s1["reason"], s1.get("reason", ""))

# 5 验收通过 -> 绿勾
second = app.cur_day()["items"][1]["id"]
app.state["items"][second] = {"status": "pending", "ts": 0, "reason": ""}
with open(TMP / "verify-result.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"id": second, "verdict": "pass", "reason": ""}, ensure_ascii=False) + "\n")
app.apply_results()
check("通过变绿勾", app.state["items"][second]["status"] == "ok")

# 6 外部程序改写 tasks.json -> 看板自动跟随
t0 = json.loads((TMP / "tasks.json").read_text(encoding="utf-8"))
t0["days"][0]["items"].append({"id": "ext-1", "text": "外部 AI 加的一条", "check": "看得见就行"})
(TMP / "tasks.json").write_text(json.dumps(t0, ensure_ascii=False), encoding="utf-8")
time.sleep(0.05)
app.poll()
check("外部改写 tasks.json 后自动跟随",
      any(r["item"]["id"] == "ext-1" for r in app.rows.values()))

# 7 文件被写坏时保留上一份好数据
(TMP / "tasks.json").write_text('{"days": [', encoding="utf-8")
time.sleep(0.05)
app.poll()
kept = any(r["item"]["id"] == "ext-1" for r in app.rows.values())
check("坏 JSON 不覆盖当前内容", kept)

root.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\nRESULT:", "ALL PASS" if ok else "HAS FAILURE")
sys.exit(0 if ok else 1)
