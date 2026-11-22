# -*- coding: utf-8 -*-
"""桌面待办侧边栏 · 主程序。

- 勾选 = 提交验收（写 verify-queue.jsonl + 建成果文件夹）
- 外部把结论写进 verify-result.jsonl：pass -> 绿勾；fail -> 自动去勾并显示原因
- 左边缘拖宽度，下边缘拖高度，Ctrl+滚轮调透明度
- ⚙ 改外观，✎ 改内容，› 进下一天
"""
import json
import os
import subprocess
import time
import tkinter as tk
from tkinter import font as tkfont

import dialogs
import store


class App:
    def __init__(self, root):
        self.root = root
        self.ui = dict(store.DEFAULT_UI)
        self.ui.update(store.load(store.UI, {}))
        self.state = store.load(store.STATE, {"items": {}, "appliedResults": 0})
        self.state.setdefault("items", {})
        self.state.setdefault("appliedResults", 0)
        self.tasks = store.load_tasks()
        self.tasks_mtime = self._mtime(store.TASKS)
        self.rows = {}
        self.drag = None
        self._colors()
        self._fonts()
        self._window()
        self._build()
        self.root.after(300, self.poll)

    # ---------------- 基础 ----------------
    def _mtime(self, p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0

    def _colors(self):
        self.bg = self.ui.get("bg_color", "#000000")
        self.fg, self.dim, self.faint = store.fg_colors(self.ui.get("fg_mode", "light"))
        self.line = "#4a4a4a" if self.ui.get("fg_mode") == "dark" else "#3a3a3a"
        self.ok = "#12a150" if self.ui.get("fg_mode") == "dark" else "#34d399"
        self.bad = "#c0392b" if self.ui.get("fg_mode") == "dark" else "#f87171"

    def _fonts(self):
        fam = "Microsoft YaHei UI"
        s = int(self.ui.get("font_size", 10))
        self.f_body = tkfont.Font(family=fam, size=s)
        self.f_body_over = tkfont.Font(family=fam, size=s, overstrike=True)
        self.f_small = tkfont.Font(family=fam, size=max(7, s - 1))
        self.f_head = tkfont.Font(family=fam, size=s + 1, weight="bold")
        self.f_box = tkfont.Font(family="Segoe UI Symbol", size=s + 5)

    @property
    def W(self):
        return int(self.ui.get("width", 340))

    def H(self):
        h = int(self.ui.get("height", 0) or 0)
        max_h = self.root.winfo_screenheight() - 40
        if h <= 0:
            h = self.root.winfo_screenheight() - 60
        return max(240, min(h, max_h))

    def _geometry(self):
        self.root.geometry("%dx%d+%d+%d" % (
            self.W, self.H(),
            self.root.winfo_screenwidth() - self.W - 12, 16))

    def _window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        try:
            r.attributes("-alpha", float(self.ui.get("alpha", 0.66)))
        except tk.TclError:
            pass
        r.configure(bg=self.bg)
        self._geometry()
        r.bind("<Escape>", lambda e: self.quit_all())
        r.bind("<Control-MouseWheel>", self.on_alpha_wheel)

    # ---------------- 布局 ----------------
    def _grip(self, side, cursor):
        g = tk.Frame(self.root, bg=self.bg, cursor=cursor)
        if side == "bottom":
            g.config(height=7)
            g.pack(side="bottom", fill="x")
            g.bind("<ButtonPress-1>", self.on_v_start)
            g.bind("<B1-Motion>", self.on_v_move)
        else:
            g.config(width=7)
            g.pack(side="left", fill="y")
            g.bind("<ButtonPress-1>", self.on_h_start)
            g.bind("<B1-Motion>", self.on_h_move)
        g.bind("<ButtonRelease-1>", self.on_drag_end)
        g.bind("<Enter>", lambda e: g.config(bg=self.line))
        g.bind("<Leave>", lambda e: g.config(bg=self.bg))
        return g

    def _build(self):
        self._grip("bottom", "sb_v_double_arrow")
        self.grip_h = self._grip("left", "sb_h_double_arrow")

        main = tk.Frame(self.root, bg=self.bg)
        main.pack(side="left", fill="both", expand=True)

        head = tk.Frame(main, bg=self.bg)
        head.pack(fill="x", padx=(12, 10), pady=(10, 2))
        tk.Label(head, text="今日待办", font=self.f_head, bg=self.bg, fg=self.fg).pack(side="left")
        for txt, cmd in (("✕", self.quit_all), ("✎", self.open_editor), ("⚙", self.open_settings)):
            lb = tk.Label(head, text=txt, font=self.f_small, bg=self.bg, fg=self.faint, cursor="hand2")
            lb.pack(side="right", padx=(8, 0))
            lb.bind("<Button-1>", lambda e, c=cmd: c())

        box = tk.Frame(main, bg=self.bg)
        box.pack(fill="x", padx=(12, 10), pady=(2, 6))
        self.lbl_day = tk.Label(box, text="", font=self.f_small, bg=self.bg, fg=self.dim)
        self.lbl_day.pack(anchor="w")
        nav = tk.Frame(box, bg=self.bg)
        nav.pack(anchor="w", pady=(4, 0))
        self.btn_prev = tk.Label(nav, text="‹ 上一天", font=self.f_small, bg=self.bg, fg=self.faint, cursor="hand2")
        self.btn_prev.pack(side="left")
        self.btn_next = tk.Label(nav, text="下一天 ›", font=self.f_small, bg=self.bg, fg=self.faint, cursor="hand2")
        self.btn_next.pack(side="left", padx=(14, 0))
        self.btn_prev.bind("<Button-1>", lambda e: self.change_day(-1))
        self.btn_next.bind("<Button-1>", lambda e: self.change_day(1))

        self.today_box = tk.Frame(main, bg=self.bg)
        self.today_box.pack(fill="x", padx=(12, 10))

        tk.Frame(main, bg=self.line, height=1).pack(fill="x", padx=12, pady=(8, 8))

        wk = tk.Frame(main, bg=self.bg)
        wk.pack(fill="x", padx=(12, 10))
        tk.Label(wk, text="本周待办", font=self.f_head, bg=self.bg, fg=self.fg).pack(anchor="w")
        self.week_sub = tk.Label(wk, text="", font=self.f_small, bg=self.bg, fg=self.dim)
        self.week_sub.pack(anchor="w", pady=(0, 4))
        self.week_box = tk.Frame(main, bg=self.bg)
        self.week_box.pack(fill="x", padx=(12, 10))

        foot = tk.Frame(main, bg=self.bg)
        foot.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        self.lbl_hint = tk.Label(foot, text="", font=self.f_small, bg=self.bg, fg=self.dim,
                                 justify="left")
        self.lbl_hint.pack(anchor="w")
        l2 = tk.Frame(foot, bg=self.bg)
        l2.pack(fill="x", pady=(3, 0))
        self.lbl_balance = tk.Label(l2, text="", font=self.f_small, bg=self.bg, fg=self.dim)
        self.lbl_balance.pack(side="left")
        d = tk.Label(l2, text="📁 成果", font=self.f_small, bg=self.bg, fg=self.dim, cursor="hand2")
        d.pack(side="right")
        d.bind("<Button-1>", lambda e: self.open_today_dir())

        self.render()

    # ---------------- 数据 ----------------
    def days(self):
        d = self.tasks.get("days")
        if d:
            return d
        old = self.tasks.get("today")
        if old is not None:
            return [{"date": self.tasks.get("date", ""), "label": "", "items": old}]
        return []

    def day_index(self):
        n = len(self.days())
        if n == 0:
            return 0
        return max(0, min(int(self.ui.get("dayIndex", 0)), n - 1))

    def cur_day(self):
        ds = self.days()
        return ds[self.day_index()] if ds else {"date": "", "label": "", "items": []}

    def day_complete(self):
        items = self.cur_day().get("items", [])
        return bool(items) and all(
            self.state["items"].get(i["id"], {}).get("status") in ("pending", "ok") for i in items)

    def change_day(self, step):
        ds = self.days()
        i = self.day_index()
        if step > 0:
            if not self.day_complete():
                return self.flash("今日还有没勾的，先勾完再进下一天")
            if i >= len(ds) - 1:
                return self.flash("已经是最后一天了")
        ni = i + step
        if ni < 0 or ni >= len(ds):
            return
        self.ui["dayIndex"] = ni
        store.save(store.UI, self.ui)
        self.render()
        self.flash("已进入 %s %s" % (ds[ni].get("label", ""), ds[ni].get("date", "")))

    # ---------------- 渲染 ----------------
    def make_row(self, parent, item, scope, wrap):
        outer = tk.Frame(parent, bg=self.bg)
        outer.pack(fill="x", pady=2)
        row = tk.Frame(outer, bg=self.bg, cursor="hand2")
        row.pack(fill="x")
        box = tk.Label(row, text="☐", font=self.f_box, bg=self.bg, fg=self.dim, width=2, cursor="hand2")
        box.pack(side="left", anchor="n")
        body = tk.Frame(row, bg=self.bg)
        body.pack(side="left", fill="x", expand=True)
        txt = tk.Label(body, text=item.get("text", ""), font=self.f_body, bg=self.bg, fg=self.fg,
                       wraplength=wrap, justify="left", anchor="w", cursor="hand2")
        txt.pack(fill="x")
        note = tk.Label(outer, text="", font=self.f_small, bg=self.bg, fg=self.bad,
                        wraplength=wrap, justify="left", anchor="w")
        for w in (row, box, body, txt):
            w.bind("<Button-1>", lambda e, i=item["id"]: self.toggle(i))
        return dict(item=item, scope=scope, outer=outer, box=box, txt=txt, note=note)

    def render(self):
        for f in (self.today_box, self.week_box):
            for w in f.winfo_children():
                w.destroy()
        self.rows = {}
        wrap = max(120, self.W - 82)
        day = self.cur_day()
        idx = self.day_index()
        total = len(self.days())
        self.lbl_day.config(
            text=("%s  %s   （第 %d/%d 天）" % (day.get("label", ""), day.get("date", ""), idx + 1, total))
            if total else "")

        for item in day.get("items", []):
            self.rows[item["id"]] = self.make_row(self.today_box, item, "today", wrap)
        for item in self.tasks.get("week", []):
            self.rows[item["id"]] = self.make_row(self.week_box, item, "week", wrap)

        meta = self.tasks.get("meta", {})
        if meta:
            self.lbl_balance.config(text="余额 %s/%s 笔" % (meta.get("balance", "?"), meta.get("total", "?")))
        self.week_sub.config(text=self.tasks.get("meta", {}).get("week", ""))
        self.lbl_hint.config(wraplength=max(120, self.W - 34))

        self.btn_next.config(fg=self.fg if (self.day_complete() and idx < total - 1) else self.faint)
        self.btn_prev.config(fg=self.fg if idx > 0 else self.faint)
        self.refresh_all()

    def refresh_all(self):
        for iid, r in self.rows.items():
            st = self.state["items"].get(iid, {})
            s = st.get("status", "todo")
            if s == "ok":
                r["box"].config(text="☑", fg=self.ok)
                r["txt"].config(font=self.f_body_over, fg=self.dim)
                r["note"].pack_forget()
            elif s == "pending":
                r["box"].config(text="⏳", fg=self.fg)
                r["txt"].config(font=self.f_body, fg=self.fg)
                r["note"].config(text="已提交，等验收…", fg=self.dim)
                r["note"].pack(anchor="w", pady=(0, 2))
            else:
                r["box"].config(text="☐", fg=self.dim)
                r["txt"].config(font=self.f_body, fg=self.fg)
                if st.get("reason"):
                    r["note"].config(text="未通过：" + st["reason"], fg=self.bad)
                    r["note"].pack(anchor="w", pady=(0, 2))
                else:
                    r["note"].pack_forget()
        items = self.cur_day().get("items", [])
        ok_n = sum(1 for i in items if self.state["items"].get(i["id"], {}).get("status") == "ok")
        pend_n = sum(1 for i in items if self.state["items"].get(i["id"], {}).get("status") == "pending")
        if items:
            self.lbl_hint.config(text="今日 %d/%d 已验收 · %d 待验收　勾＝提交验收" % (ok_n, len(items), pend_n))

    def flash(self, msg):
        self.lbl_hint.config(text=msg)

    # ---------------- 动作 ----------------
    def today_dir(self):
        d = self.cur_day().get("date") or time.strftime("%Y-%m-%d")
        return store.OUTDIR / d

    def open_today_dir(self):
        p = self.today_dir()
        p.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(p))
        except Exception:
            subprocess.Popen(["explorer", str(p)])

    def toggle(self, iid):
        st = self.state["items"].get(iid, {})
        cur = st.get("status", "todo")
        if cur == "pending":
            return self.flash("已提交，等验收（不要重复勾）")
        if cur == "ok":
            return self.flash("已验收通过")
        r = self.rows[iid]
        item = r["item"]
        d = self.today_dir() / iid
        d.mkdir(parents=True, exist_ok=True)
        tip = d / "放这里.txt"
        if not tip.exists():
            hint = item.get("art") or "把成果文件（截图 / 代码 / 文档 / 链接）放进这个文件夹。"
            tip.write_text("待办：%s\n\n要放什么：%s\n" % (item.get("text", ""), hint), encoding="utf-8")
        ts = time.time()
        self.state["items"][iid] = dict(status="pending", ts=ts, reason="")
        store.save(store.STATE, self.state)
        with open(store.QUEUE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": iid, "scope": r["scope"], "text": item.get("text", ""),
                                "dir": str(d), "ts": ts}, ensure_ascii=False) + "\n")
        self.render()
        self.flash("已提交 → 成果放：%s" % d.name)
        try:
            os.startfile(str(d))
        except Exception:
            pass

    def apply_results(self):
        lines = store.read_lines(store.RESULTS)
        n = self.state.get("appliedResults", 0)
        if len(lines) <= n:
            return
        for line in lines[n:]:
            try:
                res = json.loads(line)
            except Exception:
                continue
            st = self.state["items"].get(res.get("id"))
            if not st or st.get("status") != "pending":
                continue
            if res.get("verdict") == "pass":
                st["status"] = "ok"
                st["reason"] = ""
            else:
                st["status"] = "todo"
                st["reason"] = res.get("reason", "成果不足")
        self.state["appliedResults"] = len(lines)
        store.save(store.STATE, self.state)
        self.render()

    # ---------------- 设置 / 编辑 ----------------
    def apply_ui(self, new_ui):
        self.ui.update(new_ui)
        store.save(store.UI, self.ui)
        self._colors()
        self._fonts()
        self.root.configure(bg=self.bg)
        self.root.attributes("-alpha", float(self.ui.get("alpha", 0.66)))
        self._geometry()
        for w in self.root.winfo_children():
            w.destroy()
        self._build()

    def open_settings(self):
        dlg = dialogs.SettingsDialog(self.root, self.ui)
        self.root.wait_window(dlg)
        if dlg.result:
            self.apply_ui(dlg.result)

    def open_editor(self):
        dlg = dialogs.ContentEditor(self.root, self.tasks)
        self.root.wait_window(dlg)
        if dlg.result:
            self.tasks = dlg.result
            self.tasks_mtime = self._mtime(store.TASKS)
            self.render()
            self.flash("内容已保存")

    # ---------------- 拖拽 ----------------
    def on_h_start(self, e):
        self.drag = ("w", e.x_root, self.W)

    def on_v_start(self, e):
        self.drag = ("h", e.y_root, self.H())

    def on_h_move(self, e):
        if not self.drag or self.drag[0] != "w":
            return
        _, x0, w0 = self.drag
        self.ui["width"] = store.clamp(w0 + (x0 - e.x_root), "width")
        self._geometry()

    def on_v_move(self, e):
        if not self.drag or self.drag[0] != "h":
            return
        _, y0, h0 = self.drag
        self.ui["height"] = store.clamp(h0 + (e.y_root - y0), "height")
        self._geometry()

    def on_drag_end(self, e):
        if not self.drag:
            return
        self.drag = None
        store.save(store.UI, self.ui)
        self.render()
        for w in self.root.winfo_children():
            if isinstance(w, tk.Frame):
                w.config(bg=self.bg)

    def on_alpha_wheel(self, e):
        a = float(self.ui.get("alpha", 0.66)) + (0.04 if e.delta > 0 else -0.04)
        a = max(0.30, min(0.95, round(a, 2)))
        self.ui["alpha"] = a
        store.save(store.UI, self.ui)
        self.root.attributes("-alpha", a)
        self.flash("透明度 %.2f" % a)

    # ---------------- 循环 ----------------
    def poll(self):
        try:
            mt = self._mtime(store.TASKS)
            if mt != self.tasks_mtime:
                self.tasks_mtime = mt
                # 外部程序可能在写文件写到一半，解析失败时保留上一份好的数据
                new = store.load(store.TASKS, None)
                if isinstance(new, dict) and isinstance(new.get("days", new.get("today")), list):
                    self.tasks = new
                    self.render()
            self.apply_results()
        except Exception:
            pass
        self.root.after(1200, self.poll)

    def quit_all(self):
        try:
            store.save(store.STATE, self.state)
            store.save(store.UI, self.ui)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    root.title("今日待办")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
