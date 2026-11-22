# -*- coding: utf-8 -*-
"""设置窗口与内容编辑窗口。"""
import copy
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog

import store

BG = "#202020"
CARD = "#2a2a2a"
FG = "#eeeeee"
DIM = "#9a9a9a"


def _entry(parent, value, width=8):
    e = tk.Entry(parent, width=width, bg=CARD, fg=FG, insertbackground=FG,
                 relief="flat", highlightthickness=1,
                 highlightbackground="#3a3a3a", highlightcolor="#7aa7ff")
    e.insert(0, str(value))
    return e


class SettingsDialog(tk.Toplevel):
    """外观设置：宽高 / 透明度 / 字号 / 背景色 / 文字深浅。"""

    def __init__(self, master, ui):
        super().__init__(master)
        self.title("看板设置")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.ui = dict(store.DEFAULT_UI)
        self.ui.update(ui)
        self.color = self.ui.get("bg_color", "#000000")
        self._build()
        self.transient(master)
        self.grab_set()

    def _build(self):
        pad = dict(padx=10, pady=4)
        box = tk.Frame(self, bg=BG)
        box.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(box, text="尺寸", bg=BG, fg=DIM, font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w", pady=(0, 2))
        f1 = tk.Frame(box, bg=BG)
        f1.grid(row=1, column=0, columnspan=3, sticky="w", **pad)
        tk.Label(f1, text="宽", bg=BG, fg=FG).pack(side="left")
        self.e_w = _entry(f1, self.ui.get("width", 340))
        self.e_w.pack(side="left", padx=(4, 12))
        tk.Label(f1, text="高（0=自动）", bg=BG, fg=FG).pack(side="left")
        self.e_h = _entry(f1, self.ui.get("height", 0))
        self.e_h.pack(side="left", padx=(4, 0))

        tk.Label(box, text="外观", bg=BG, fg=DIM, font=("Microsoft YaHei UI", 9)).grid(row=2, column=0, sticky="w", pady=(10, 2))

        r3 = tk.LabelFrame(box, text="透明度", bg=BG, fg=DIM, bd=1, relief="groove")
        r3.grid(row=3, column=0, columnspan=3, sticky="we", **pad)
        self.s_alpha = tk.Scale(r3, from_=0.30, to=1.0, resolution=0.02, orient="horizontal",
                                bg=BG, fg=FG, troughcolor=CARD, highlightthickness=0,
                                length=260, command=lambda v: None)
        self.s_alpha.set(float(self.ui.get("alpha", 0.66)))
        self.s_alpha.pack(fill="x", padx=6, pady=2)

        r4 = tk.LabelFrame(box, text="字号", bg=BG, fg=DIM, bd=1, relief="groove")
        r4.grid(row=4, column=0, columnspan=3, sticky="we", **pad)
        self.s_font = tk.Scale(r4, from_=8, to=16, resolution=1, orient="horizontal",
                               bg=BG, fg=FG, troughcolor=CARD, highlightthickness=0, length=260)
        self.s_font.set(int(self.ui.get("font_size", 10)))
        self.s_font.pack(fill="x", padx=6, pady=2)

        r5 = tk.LabelFrame(box, text="背景色", bg=BG, fg=DIM, bd=1, relief="groove")
        r5.grid(row=5, column=0, columnspan=3, sticky="we", **pad)
        sw = tk.Frame(r5, bg=BG)
        sw.pack(anchor="w", padx=6, pady=6)
        self.swatches = []
        for i, (hexv, name) in enumerate(store.PRESETS):
            f = tk.Frame(sw, bg=hexv, width=26, height=26, cursor="hand2",
                         highlightthickness=2, highlightbackground=BG)
            f.grid(row=i // 4, column=i % 4, padx=3, pady=3)
            f.bind("<Button-1>", lambda e, c=hexv: self.pick(c))
            self.swatches.append((hexv, f))
        self.btn_custom = tk.Button(r5, text="自定义颜色…", bg=CARD, fg=FG, relief="flat",
                                    activebackground="#3a3a3a", activeforeground=FG,
                                    command=self.custom)
        self.btn_custom.pack(anchor="w", padx=6, pady=(0, 6))
        self.lbl_color = tk.Label(r5, text=self.color, bg=BG, fg=DIM)
        self.lbl_color.pack(anchor="w", padx=6)

        r6 = tk.LabelFrame(box, text="文字", bg=BG, fg=DIM, bd=1, relief="groove")
        r6.grid(row=6, column=0, columnspan=3, sticky="we", **pad)
        self.v_mode = tk.StringVar(value=self.ui.get("fg_mode", "light"))
        tk.Radiobutton(r6, text="深底浅字", variable=self.v_mode, value="light",
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                       activeforeground=FG, highlightthickness=0).pack(side="left", padx=6)
        tk.Radiobutton(r6, text="浅底深字", variable=self.v_mode, value="dark",
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                       activeforeground=FG, highlightthickness=0).pack(side="left", padx=6)

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(bar, text="保存", bg="#2f6ee0", fg="white", relief="flat", width=10,
                  command=self.ok).pack(side="right", padx=4)
        tk.Button(bar, text="取消", bg=CARD, fg=FG, relief="flat", width=8,
                  command=self.destroy).pack(side="right", padx=4)

        self.pick(self.color)

    def pick(self, hexv):
        self.color = hexv
        self.lbl_color.config(text=hexv)
        for c, f in self.swatches:
            f.config(highlightbackground="#7aa7ff" if c.lower() == hexv.lower() else BG)

    def custom(self):
        rgb, hexv = colorchooser.askcolor(color=self.color, title="选择背景色")
        if hexv:
            self.pick(hexv)

    def ok(self):
        try:
            w = int(float(self.e_w.get()))
        except Exception:
            w = self.ui.get("width", 340)
        try:
            h = int(float(self.e_h.get()))
        except Exception:
            h = 0
        self.ui.update(
            width=store.clamp(w, "width"),
            height=0 if h <= 0 else store.clamp(h, "height"),
            alpha=round(float(self.s_alpha.get()), 2),
            font_size=store.clamp(int(self.s_font.get()), "font"),
            bg_color=self.color,
            fg_mode=self.v_mode.get(),
        )
        self.result = self.ui
        self.destroy()


class ContentEditor(tk.Toplevel):
    """内容编辑：日期 / 当天任务 / 本周任务。"""

    def __init__(self, master, tasks):
        super().__init__(master)
        self.title("编辑待办内容")
        self.configure(bg=BG)
        self.result = None
        self.tasks = copy.deepcopy(tasks)
        self.tasks.setdefault("days", [])
        self.tasks.setdefault("week", [])
        self.tasks.setdefault("meta", {})
        self._build()
        self.refresh_days()
        self._select_day(0)
        self.refresh_week()
        self.transient(master)
        self.grab_set()

    def _lb(self, parent, height=8):
        lb = tk.Listbox(parent, height=height, bg=CARD, fg=FG, selectbackground="#2f6ee0",
                        selectforeground="white", relief="flat", highlightthickness=1,
                        highlightbackground="#3a3a3a", activestyle="none")
        return lb

    def _build(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(wrap, bg=BG)
        left.pack(side="left", fill="y")
        tk.Label(left, text="日期", bg=BG, fg=DIM).pack(anchor="w")
        self.days_lb = self._lb(left, 10)
        self.days_lb.pack(fill="y", pady=4)
        self.days_lb.bind("<<ListboxSelect>>", self.on_day)
        row = tk.Frame(left, bg=BG)
        row.pack(fill="x")
        for t, cmd in (("新增一天", self.add_day), ("删除这天", self.del_day)):
            tk.Button(row, text=t, bg=CARD, fg=FG, relief="flat", command=cmd).pack(side="left", padx=(0, 4), pady=2)

        right = tk.Frame(wrap, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        tk.Label(right, text="当天任务", bg=BG, fg=DIM).pack(anchor="w")
        self.items_lb = self._lb(right, 9)
        self.items_lb.pack(fill="x", pady=4)
        btns = tk.Frame(right, bg=BG)
        btns.pack(fill="x")
        for t, cmd in (("新增", self.add_item), ("编辑", self.edit_item),
                       ("删除", self.del_item), ("上移", lambda: self.move(self.items_lb, self.cur_items(), -1)),
                       ("下移", lambda: self.move(self.items_lb, self.cur_items(), 1))):
            tk.Button(btns, text=t, bg=CARD, fg=FG, relief="flat", width=6,
                      command=cmd).pack(side="left", padx=(0, 4))

        tk.Label(right, text="本周任务", bg=BG, fg=DIM).pack(anchor="w", pady=(12, 0))
        self.week_lb = self._lb(right, 5)
        self.week_lb.pack(fill="x", pady=4)
        btns2 = tk.Frame(right, bg=BG)
        btns2.pack(fill="x")
        for t, cmd in (("新增", self.add_week), ("编辑", self.edit_week),
                       ("删除", self.del_week), ("上移", lambda: self.move(self.week_lb, self.tasks["week"], -1)),
                       ("下移", lambda: self.move(self.week_lb, self.tasks["week"], 1))):
            tk.Button(btns2, text=t, bg=CARD, fg=FG, relief="flat", width=6,
                      command=cmd).pack(side="left", padx=(0, 4))

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(bar, text="改完记得点保存；保存后看板 1 秒内自动刷新", bg=BG, fg=DIM).pack(side="left")
        tk.Button(bar, text="保存", bg="#2f6ee0", fg="white", relief="flat", width=10,
                  command=self.ok).pack(side="right", padx=4)
        tk.Button(bar, text="取消", bg=CARD, fg=FG, relief="flat", width=8,
                  command=self.destroy).pack(side="right", padx=4)

    # ---------- days ----------
    def refresh_days(self):
        self.days_lb.delete(0, "end")
        for d in self.tasks["days"]:
            self.days_lb.insert("end", "%s  %s" % (d.get("label", ""), d.get("date", "")))

    def _select_day(self, i):
        if not self.tasks["days"]:
            self.items_lb.delete(0, "end")
            return
        i = max(0, min(i, len(self.tasks["days"]) - 1))
        self.days_lb.selection_clear(0, "end")
        self.days_lb.selection_set(i)
        self.days_lb.see(i)
        self.refresh_items()

    def cur_day(self):
        sel = self.days_lb.curselection()
        if not sel or not self.tasks["days"]:
            return None
        return self.tasks["days"][sel[0]]

    def cur_items(self):
        d = self.cur_day()
        return d["items"] if d else []

    def on_day(self, _e=None):
        self.refresh_items()

    def refresh_items(self):
        self.items_lb.delete(0, "end")
        for it in self.cur_items():
            self.items_lb.insert("end", it.get("text", ""))

    def add_day(self):
        date = simpledialog.askstring("新增一天", "日期（YYYY-MM-DD）：", parent=self,
                                      initialvalue="2026-12-01")
        if not date:
            return
        label = simpledialog.askstring("新增一天", "标签（如 周一）：", parent=self, initialvalue="")
        self.tasks["days"].append({"date": date.strip(), "label": (label or "").strip(), "items": []})
        self.refresh_days()
        self._select_day(len(self.tasks["days"]) - 1)

    def del_day(self):
        i = self.days_lb.curselection()
        if not i:
            return
        if not messagebox.askyesno("删除", "删掉这一天和它的任务？", parent=self):
            return
        self.tasks["days"].pop(i[0])
        self.refresh_days()
        self._select_day(max(0, i[0] - 1))

    # ---------- items ----------
    def _new_id(self, date):
        base = "".join(ch for ch in date if ch.isdigit()) or "item"
        used = set()
        for d in self.tasks["days"]:
            for it in d.get("items", []):
                used.add(it.get("id"))
        n = 1
        while ("%s-%d" % (base, n)) in used:
            n += 1
        return "%s-%d" % (base, n)

    def add_item(self):
        d = self.cur_day()
        if not d:
            messagebox.showinfo("提示", "先选一天", parent=self)
            return
        text = simpledialog.askstring("新增任务", "任务内容：", parent=self)
        if not text:
            return
        d["items"].append({"id": self._new_id(d.get("date", "")), "text": text.strip()})
        self.refresh_items()

    def edit_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        items = self.cur_items()
        it = items[sel[0]]
        text = simpledialog.askstring("编辑任务", "任务内容：", parent=self, initialvalue=it.get("text", ""))
        if text:
            it["text"] = text.strip()
            self.refresh_items()

    def del_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        self.cur_items().pop(sel[0])
        self.refresh_items()

    # ---------- week ----------
    def refresh_week(self):
        self.week_lb.delete(0, "end")
        for it in self.tasks["week"]:
            self.week_lb.insert("end", it.get("text", ""))

    def add_week(self):
        text = simpledialog.askstring("新增本周任务", "内容：", parent=self)
        if not text:
            return
        n = len(self.tasks["week"]) + 1
        used = {w.get("id") for w in self.tasks["week"]}
        while ("w%d" % n) in used:
            n += 1
        self.tasks["week"].append({"id": "w%d" % n, "text": text.strip()})
        self.refresh_week()

    def edit_week(self):
        sel = self.week_lb.curselection()
        if not sel:
            return
        it = self.tasks["week"][sel[0]]
        text = simpledialog.askstring("编辑", "内容：", parent=self, initialvalue=it.get("text", ""))
        if text:
            it["text"] = text.strip()
            self.refresh_week()

    def del_week(self):
        sel = self.week_lb.curselection()
        if not sel:
            return
        self.tasks["week"].pop(sel[0])
        self.refresh_week()

    # ---------- move / save ----------
    def move(self, lb, data, delta):
        sel = lb.curselection()
        if not sel or not data:
            return
        i = sel[0]
        j = i + delta
        if j < 0 or j >= len(data):
            return
        data[i], data[j] = data[j], data[i]
        if lb is self.items_lb:
            self.refresh_items()
        else:
            self.refresh_week()
        lb.selection_clear(0, "end")
        lb.selection_set(j)

    def ok(self):
        store.save(store.TASKS, self.tasks)
        self.result = self.tasks
        self.destroy()
