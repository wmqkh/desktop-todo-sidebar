# -*- coding: utf-8 -*-
"""桌面待办侧边栏 · 主程序。

- 拖标题栏移动窗口；四个边 + 四个角都能拉伸
- 勾选 = 提交验收（写 verify-queue.jsonl + 建成果文件夹）
- 外部把结论写进 verify-result.jsonl：pass -> 绿勾；fail -> 自动去勾并显示原因
- 滚轮滚动内容，Ctrl+滚轮调透明度，右键出菜单
"""
import json
import os
import subprocess
import time
import tkinter as tk
from tkinter import font as tkfont

import dialogs
import store

BASE = store.BASE

EDGE = 6          # 边缘判定像素
HEADER_H = 38     # 标题栏可拖动高度
MIN_W, MIN_H = 200, 140
BALL = 56         # 收起后小球的直径
MAGIC = "#010203" # 透明色键（小球四角抠掉用）


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
        self.src_snap = self._src_snapshot()   # 启动时以当前代码为基线，避免误重启
        self.src_changed_at = 0
        self.rows = {}
        self.drag = None
        self._colors()
        self._fonts()
        self._geometry_from_ui()
        self._window()
        self.expanded_alpha = float(self.ui.get("alpha", 0.66))
        if self.ui.get("collapsed"):
            self.collapsed_pos = (self.gx + self.gw - BALL, self.gy)
            self._build_collapsed()
        else:
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

    # ---------------- 几何 ----------------
    def _geometry_from_ui(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = store.clamp(int(self.ui.get("width") or 340), "width")
        h = int(self.ui.get("height") or 0) or (sh - 60)
        h = max(MIN_H, min(h, sh - 20))
        x = self.ui.get("x")
        y = self.ui.get("y")
        x = (sw - w - 12) if x is None else int(x)
        y = 16 if y is None else int(y)
        x = max(80 - w, min(x, sw - 80))
        y = max(0, min(y, sh - 40))
        self.gw, self.gh, self.gx, self.gy = w, h, x, y

    def _apply_geometry(self):
        self.root.geometry("%dx%d+%d+%d" % (self.gw, self.gh, self.gx, self.gy))

    def _save_geometry(self):
        self.ui.update(x=self.gx, y=self.gy, width=self.gw, height=self.gh)
        store.save(store.UI, self.ui)

    def reset_position(self):
        if self.ui.get("collapsed"):
            self.expand()
        self.ui.update(x=None, y=None, width=340, height=0)
        store.save(store.UI, self.ui)
        self._geometry_from_ui()
        self._apply_geometry()
        self.render()
        self.flash("已回到右上角默认尺寸")

    def _window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        try:
            r.attributes("-alpha", float(self.ui.get("alpha", 0.66)))
        except tk.TclError:
            pass
        r.configure(bg=self.bg)
        self._apply_geometry()
        r.bind("<Escape>", lambda e: self.quit_all())
        r.bind("<ButtonPress-1>", self.on_press)
        r.bind("<B1-Motion>", self.on_motion)
        r.bind("<ButtonRelease-1>", self.on_release)
        r.bind("<Motion>", self.on_hover)
        r.bind("<MouseWheel>", self.on_wheel)
        r.bind("<Button-3>", self.on_menu)

    # ---------------- 布局 ----------------
    def _build(self):
        main = tk.Frame(self.root, bg=self.bg)
        main.pack(fill="both", expand=True)

        head = tk.Frame(main, bg=self.bg, cursor="fleur")
        head.pack(fill="x", padx=(12, 10), pady=(8, 2))
        tk.Label(head, text="今日待办", font=self.f_head, bg=self.bg, fg=self.fg,
                 cursor="fleur").pack(side="left")
        self.lbl_prog = tk.Label(head, text="", font=self.f_small, bg=self.bg, fg=self.faint,
                                 cursor="fleur")
        self.lbl_prog.pack(side="left", padx=(8, 0))
        for txt, cmd in (("✕", self.quit_all), ("✎", self.open_editor),
                         ("⚙", self.open_settings), ("—", self.collapse)):
            lb = tk.Label(head, text=txt, font=self.f_small, bg=self.bg, fg=self.faint, cursor="hand2")
            lb.pack(side="right", padx=(8, 0))
            lb.bind("<Button-1>", lambda e, c=cmd: self._icon(c))

        self.cv = tk.Canvas(main, bg=self.bg, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=self.bg)
        self.cvw = self.cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_conf)
        self.cv.bind("<Configure>", self._on_canvas_conf)

        body = self.inner
        box = tk.Frame(body, bg=self.bg)
        box.pack(fill="x", padx=(12, 10), pady=(2, 6))
        self.lbl_day = tk.Label(box, text="", font=self.f_small, bg=self.bg, fg=self.dim)
        self.lbl_day.pack(anchor="w")
        nav = tk.Frame(box, bg=self.bg)
        nav.pack(anchor="w", pady=(4, 0))
        self.btn_prev = tk.Label(nav, text="‹ 上一天", font=self.f_small, bg=self.bg,
                                 fg=self.faint, cursor="hand2")
        self.btn_prev.pack(side="left")
        self.btn_next = tk.Label(nav, text="下一天 ›", font=self.f_small, bg=self.bg,
                                 fg=self.faint, cursor="hand2")
        self.btn_next.pack(side="left", padx=(14, 0))
        self.btn_prev.bind("<Button-1>", lambda e: self.change_day(-1))
        self.btn_next.bind("<Button-1>", lambda e: self.change_day(1))

        self.today_box = tk.Frame(body, bg=self.bg)
        self.today_box.pack(fill="x", padx=(12, 10))

        tk.Frame(body, bg=self.line, height=1).pack(fill="x", padx=12, pady=(8, 8))

        wk = tk.Frame(body, bg=self.bg)
        wk.pack(fill="x", padx=(12, 10))
        tk.Label(wk, text="本周待办", font=self.f_head, bg=self.bg, fg=self.fg).pack(anchor="w")
        self.week_sub = tk.Label(wk, text="", font=self.f_small, bg=self.bg, fg=self.dim)
        self.week_sub.pack(anchor="w", pady=(0, 4))
        self.week_box = tk.Frame(body, bg=self.bg)
        self.week_box.pack(fill="x", padx=(12, 10))

        foot = tk.Frame(main, bg=self.bg)
        foot.pack(side="bottom", fill="x", padx=12, pady=(2, 8))
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

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="设置…", command=self.open_settings)
        self.menu.add_command(label="编辑内容…", command=self.open_editor)
        self.menu.add_command(label="收起成小球", command=self.collapse)
        self.menu.add_separator()
        self.menu.add_command(label="回到右上角", command=self.reset_position)
        self.menu.add_command(label="退出", command=self.quit_all)

    def _icon(self, cmd):
        cmd()
        return "break"

    def _on_inner_conf(self, e):
        self.cv.configure(scrollregion=self.cv.bbox("all"))

    def _on_canvas_conf(self, e):
        self.cv.itemconfigure(self.cvw, width=e.width)

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
        if self.ui.get("collapsed"):
            self.refresh_ball()
            return
        for f in (self.today_box, self.week_box):
            for w in f.winfo_children():
                w.destroy()
        self.rows = {}
        wrap = max(110, self.gw - 82)
        day = self.cur_day()
        idx = self.day_index()
        total = len(self.days())
        if total:
            self.lbl_day.config(text="%s  %s   （第 %d/%d 天）" % (
                day.get("label", ""), day.get("date", ""), idx + 1, total))
        else:
            self.lbl_day.config(text="还没有任务，点右上角 ✎ 添加")

        for item in day.get("items", []):
            self.rows[item["id"]] = self.make_row(self.today_box, item, "today", wrap)
        for item in self.tasks.get("week", []):
            self.rows[item["id"]] = self.make_row(self.week_box, item, "week", wrap)

        meta = self.tasks.get("meta", {})
        if meta:
            self.lbl_balance.config(text="余额 %s/%s 笔" % (meta.get("balance", "?"), meta.get("total", "?")))
        self.week_sub.config(text=meta.get("week", ""))
        self.lbl_hint.config(wraplength=max(110, self.gw - 34))

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
            self.lbl_prog.config(text="%d/%d" % (ok_n + pend_n, len(items)))
        else:
            self.lbl_prog.config(text="")

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
        new = not d.exists()
        d.mkdir(parents=True, exist_ok=True)
        tip = d / "放这里.txt"
        if not tip.exists():
            hint = item.get("art") or "把成果文件（截图 / 代码 / 文档 / 链接）放进这个文件夹。"
            chk = item.get("check")
            body = "待办：%s\n\n要放什么：%s\n" % (item.get("text", ""), hint)
            if chk:
                body += "\n验收标准：%s\n" % chk
            tip.write_text(body, encoding="utf-8")
        ts = time.time()
        self.state["items"][iid] = dict(status="pending", ts=ts, reason="")
        store.save(store.STATE, self.state)
        with open(store.QUEUE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": iid, "scope": r["scope"], "text": item.get("text", ""),
                                "dir": str(d), "ts": ts}, ensure_ascii=False) + "\n")
        self.render()
        self.flash("已提交 → 成果放：%s" % d.name)
        if new and self.ui.get("auto_open_dir", True):
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
            if not st:
                continue
            # 只处理待验收的项；带 override 的结论可以推翻已有状态（供人工/AI 改判）
            if st.get("status") != "pending" and not res.get("override"):
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
        self._geometry_from_ui()
        self._apply_geometry()
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

    # ---------------- 拖动 / 缩放 ----------------
    def _zone(self, e):
        lx = e.x_root - self.gx
        ly = e.y_root - self.gy
        return (lx <= EDGE, lx >= self.gw - EDGE, ly <= EDGE, ly >= self.gh - EDGE), lx, ly

    def on_press(self, e):
        (l, r, t, b), lx, ly = self._zone(e)
        if l or r or t or b:
            self.drag = dict(mode="resize", edges=(l, r, t, b),
                             x0=e.x_root, y0=e.y_root, geo=(self.gx, self.gy, self.gw, self.gh))
        elif ly <= HEADER_H:
            self.drag = dict(mode="move", x0=e.x_root, y0=e.y_root,
                             geo=(self.gx, self.gy, self.gw, self.gh))
        else:
            self.drag = None

    def on_motion(self, e):
        d = self.drag
        if not d:
            return
        dx = e.x_root - d["x0"]
        dy = e.y_root - d["y0"]
        x0, y0, w0, h0 = d["geo"]
        if d["mode"] == "move":
            x, y, w, h = x0 + dx, y0 + dy, w0, h0
        else:
            l, r, t, b = d["edges"]
            x, y, w, h = x0, y0, w0, h0
            if l:
                w = max(MIN_W, w0 - dx)
                x = x0 + w0 - w
            if r:
                w = max(MIN_W, w0 + dx)
            if t:
                h = max(MIN_H, h0 - dy)
                y = y0 + h0 - h
            if b:
                h = max(MIN_H, h0 + dy)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = max(80 - w, min(x, sw - 80))
        y = max(0, min(y, sh - 40))
        h = min(h, sh - y)
        self.gx, self.gy, self.gw, self.gh = int(x), int(y), int(w), int(h)
        self._apply_geometry()

    def on_release(self, e):
        if not self.drag:
            return
        mode = self.drag["mode"]
        self.drag = None
        self._save_geometry()
        self.render()
        if mode == "move":
            self.flash("位置已保存")

    def on_hover(self, e):
        if self.drag:
            return
        (l, r, t, b), lx, ly = self._zone(e)
        if (l and t) or (r and b):
            cur = "size_nw_se"
        elif (r and t) or (l and b):
            cur = "size_ne_sw"
        elif l or r:
            cur = "sb_h_double_arrow"
        elif t or b:
            cur = "sb_v_double_arrow"
        elif ly <= HEADER_H:
            cur = "fleur"
        else:
            cur = ""
        try:
            self.root.config(cursor=cur)
        except tk.TclError:
            pass

    def on_wheel(self, e):
        if e.state & 0x0004:      # Ctrl -> 透明度
            a = float(self.ui.get("alpha", 0.66)) + (0.04 if e.delta > 0 else -0.04)
            a = max(0.30, min(0.95, round(a, 2)))
            self.ui["alpha"] = a
            store.save(store.UI, self.ui)
            self.root.attributes("-alpha", a)
            self.flash("透明度 %.2f" % a)
            return "break"
        try:
            self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception:
            pass
        return "break"

    def on_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()
        return "break"

    # ---------------- 收起成小球 ----------------
    def _magic(self):
        return MAGIC if self.bg.lower() != MAGIC.lower() else "#020304"

    def _supports_key(self):
        """探测当前 Tk/Windows 是否支持 transparentcolor（不支持就走方形兜底）。"""
        try:
            self.root.attributes("-transparentcolor", MAGIC)
            got = self.root.attributes("-transparentcolor")
            self.root.attributes("-transparentcolor", "")
            return bool(got)
        except tk.TclError:
            return False

    def _log(self, tag, exc_text):
        try:
            with open(BASE / "error.log", "a", encoding="utf-8") as f:
                f.write("[%s] %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), tag, exc_text))
        except Exception:
            pass

    def collapse(self):
        if self.ui.get("collapsed") or getattr(self, "_toggling", False):
            return
        self._toggling = True
        try:
            self._save_geometry()                    # 先记住展开时的位置尺寸
            self.expanded_alpha = float(self.ui.get("alpha", 0.66))
            self.collapsed_pos = (self.gx + self.gw - BALL, self.gy)
            self.ui["collapsed"] = True
            store.save(store.UI, self.ui)
            self._build_collapsed()
        except Exception:
            import traceback
            self._log("collapse 失败", traceback.format_exc())
            self.ui["collapsed"] = False
            store.save(store.UI, self.ui)
        finally:
            self._toggling = False

    def ball_text(self):
        items = self.cur_day().get("items", [])
        if not items:
            return "–"
        n = len(items)
        done = sum(1 for i in items
                   if self.state["items"].get(i["id"], {}).get("status") in ("ok", "pending"))
        if done == n:
            ok = sum(1 for i in items if self.state["items"].get(i["id"], {}).get("status") == "ok")
            return "✓" if ok == n else "%d/%d" % (done, n)
        return "%d/%d" % (done, n)

    def _draw_ball(self):
        cv = getattr(self, "ball_canvas", None)
        if cv is None:
            return
        try:
            if not cv.winfo_exists():
                return
            cv.delete("all")
            cv.create_oval(1, 1, BALL - 1, BALL - 1, fill=self.bg, outline=self.line)
            cv.create_text(BALL // 2, BALL // 2 - 9, text="待办", font=self.f_small, fill=self.dim)
            txt = self.ball_text()
            cv.create_text(BALL // 2, BALL // 2 + 9, text=txt, font=self.f_body,
                           fill=self.ok if txt == "✓" else self.fg)
        except Exception:
            import traceback
            self._log("_draw_ball 失败", traceback.format_exc())

    def refresh_ball(self):
        self._draw_ball()

    def _build_collapsed(self):
        for w in self.root.winfo_children():
            w.destroy()
        magic = self._magic()
        self.root.configure(bg=magic)
        # 先把色键开起来再画，避免先闪一个方块
        keyed = self._supports_key()
        if keyed:
            try:
                self.root.attributes("-transparentcolor", magic)
            except tk.TclError:
                keyed = False
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        x, y = getattr(self, "collapsed_pos", (self.gx, self.gy))
        self.gx, self.gy, self.gw, self.gh = int(x), int(y), BALL, BALL
        self.root.geometry("%dx%d+%d+%d" % (BALL, BALL, self.gx, self.gy))
        self.root.config(cursor="hand2")

        cv = tk.Canvas(self.root, width=BALL, height=BALL, bg=magic if keyed else self.bg,
                       highlightthickness=0, bd=0, cursor="hand2")
        cv.pack()
        self.ball_canvas = cv
        self._draw_ball()
        # 只绑画布，避免和 root 的绑定重复触发
        cv.bind("<ButtonPress-1>", self.on_ball_press)
        cv.bind("<B1-Motion>", self.on_ball_move)
        cv.bind("<ButtonRelease-1>", self.on_ball_release)
        cv.bind("<Button-3>", self.on_ball_menu)
        cv.bind("<Double-Button-1>", lambda e: "break")   # 双击不连发

    def expand(self):
        if not self.ui.get("collapsed") or getattr(self, "_toggling", False):
            return
        self._toggling = True
        try:
            self.ui["collapsed"] = False
            store.save(store.UI, self.ui)
            try:
                self.root.attributes("-transparentcolor", "")
            except tk.TclError:
                pass
            try:
                self.root.attributes("-alpha", getattr(self, "expanded_alpha",
                                                       float(self.ui.get("alpha", 0.66))))
            except tk.TclError:
                pass
            self._geometry_from_ui()
            self._apply_geometry()
            self.root.config(cursor="")
            for w in self.root.winfo_children():
                w.destroy()
            self.ball_canvas = None
            self._build()
        except Exception:
            import traceback
            self._log("expand 失败", traceback.format_exc())
        finally:
            self._toggling = False

    def on_ball_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="展开", command=self.expand)
        m.add_separator()
        m.add_command(label="退出", command=self.quit_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    def on_ball_press(self, e):
        self.ball_drag = (e.x_root, e.y_root, self.gx, self.gy)
        self.ball_moved = False

    def on_ball_move(self, e):
        d = getattr(self, "ball_drag", None)
        if not d:
            return
        x0, y0, gx, gy = d
        dx, dy = e.x_root - x0, e.y_root - y0
        if abs(dx) + abs(dy) > 4:
            self.ball_moved = True
        self.gx, self.gy = int(gx + dx), int(gy + dy)
        self.root.geometry("%dx%d+%d+%d" % (BALL, BALL, self.gx, self.gy))

    def on_ball_release(self, e):
        if not getattr(self, "ball_moved", False):
            self.expand()
        else:
            self.collapsed_pos = (self.gx, self.gy)

    # ---------------- 循环 ----------------
    def _src_snapshot(self):
        """当前源码文件的 mtime 快照，用来发现代码改动。"""
        snap = {}
        for p in sorted(BASE.glob("*.py")):
            try:
                snap[p.name] = p.stat().st_mtime
            except OSError:
                pass
        return snap

    def _dialogs_open(self):
        return any(isinstance(w, tk.Toplevel) for w in self.root.winfo_children())

    def restart_app(self):
        """请求外层守护进程重启自己（状态和几何都已落盘，不会丢）。"""
        try:
            store.save(store.STATE, self.state)
            self._save_geometry()
        except Exception:
            pass
        try:
            with open(BASE / "restart.log", "a", encoding="utf-8") as f:
                f.write("[%s] 源码变更 -> 请求重启 pid=%s\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid()))
        except Exception:
            pass
        self.root.destroy()
        os._exit(42)      # 42 = 交给 run_sidebar.py 重新拉起

    def poll(self):
        try:
            mt = self._mtime(store.TASKS)
            if mt != self.tasks_mtime:
                self.tasks_mtime = mt
                new = store.load(store.TASKS, None)
                if isinstance(new, dict) and isinstance(new.get("days", new.get("today")), list):
                    self.tasks = new
                    self.render()
            self.apply_results()
            # 源码热重载：改完 .py 不用手动重启
            if self.ui.get("auto_reload", True):
                snap = self._src_snapshot()
                if snap != self.src_snap:
                    self.src_snap = snap
                    self.src_changed_at = time.time()
                elif self.src_changed_at and time.time() - self.src_changed_at > 2.0:
                    if not self._dialogs_open():
                        self.restart_app()
        except Exception:
            pass
        self.root.after(1200, self.poll)

    def quit_all(self):
        try:
            store.save(store.STATE, self.state)
            if not self.ui.get("collapsed"):
                self._save_geometry()      # 收起时不能把小球尺寸写进展开的几何
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    root.title("今日待办")

    def log_exc(exc, val, tb):
        import traceback
        try:
            with open(BASE / "error.log", "a", encoding="utf-8") as f:
                f.write("[%s] 回调异常\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                f.write("".join(traceback.format_exception(exc, val, tb)))
        except Exception:
            pass

    root.report_callback_exception = log_exc
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
