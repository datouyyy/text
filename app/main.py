"""
DeepSeek NEXUS v2.0 — 迷你余额面板
"""
import json, sys, os, threading, time
from pathlib import Path
from datetime import datetime
import customtkinter as ctk
import requests

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

API_BALANCE = "https://api.deepseek.com/user/balance"
DATA_DIR = Path.home() / ".dsnexus"
KEYS_FILE = DATA_DIR / "keys.json"
CFG_FILE = DATA_DIR / "config.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BG0 = "#050a14"; BG1 = "#0a1020"; BG2 = "#0f1a30"; BG3 = "#162240"
NEON_CYAN = "#00f0ff"; NEON_PINK = "#ff00aa"; NEON_GREEN = "#00ff88"
NEON_GOLD = "#facc15"; NEON_RED = "#ff3355"
TEXT = "#e0e8f0"; TEXT2 = "#8899bb"; TEXT3 = "#445566"; LINE = "#1a2a44"

def load_keys():
    if KEYS_FILE.exists():
        try: return json.load(open(KEYS_FILE))
        except: pass
    return []

def save_keys(keys):
    with open(KEYS_FILE, "w") as f: json.dump(keys, f, indent=2)

def load_cfg():
    if CFG_FILE.exists():
        try: return json.load(open(CFG_FILE))
        except: pass
    return {"auto_refresh": True, "interval": 60, "ontop": False}

def save_cfg(cfg):
    with open(CFG_FILE, "w") as f: json.dump(cfg, f, indent=2)

def mask_key(k):
    return k[:6] + "●"*8 + k[-4:] if len(k) > 14 else k

def fmt(v):
    return f"¥{float(v):,.2f}"

class Nexus:
    def __init__(self):
        self.keys = load_keys()
        self.cfg = load_cfg()
        self._busy = False
        self._timer = None
        self._sel = self.keys[0] if self.keys else None
        self._bal = {}
        self._auto_on = self.cfg.get("auto_refresh", True)
        self._interval = self.cfg.get("interval", 60)
        self._ontop = self.cfg.get("ontop", False)

        self.root = ctk.CTk()
        self.root.title("DeepSeek NEXUS v2.0")
        self.root.geometry("300x280")
        self.root.resizable(False, False)
        self.root.configure(fg_color=BG0)
        if self._ontop:
            self.root.attributes("-topmost", True)

        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw-300)//2}+{(sh-280)//2}")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self._build_top()
        self._build_body()
        self._build_bot()
        self._start()

    def _build_top(self):
        top = ctk.CTkFrame(self.root, fg_color=BG1, height=38, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        ctk.CTkFrame(top, fg_color=NEON_CYAN, width=3, height=38).place(x=0, y=0)
        ctk.CTkFrame(top, fg_color=NEON_PINK, width=1, height=38).place(x=3, y=0)

        ctk.CTkLabel(top, text="DEEPSEEK NEXUS",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=NEON_CYAN
            ).place(x=10, rely=0.5, anchor="w")

        # 设置按钮
        btn_gear = ctk.CTkButton(top, text="⚙ 设置",
            width=52, height=24, fg_color="transparent", hover_color=BG3,
            font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT,
            border_width=1, border_color=LINE, corner_radius=4,
            command=self._open_settings)
        btn_gear.place(x=178, rely=0.5, anchor="center")

        # 刷新按钮
        btn_sync = ctk.CTkButton(top, text="⟳ 刷新",
            width=52, height=24, fg_color="transparent", hover_color=BG3,
            font=ctk.CTkFont(size=10, weight="bold"), text_color=NEON_CYAN,
            border_width=1, border_color=LINE, corner_radius=4,
            command=self._refresh_all)
        btn_sync.place(x=238, rely=0.5, anchor="center")

        # 置顶按钮
        self._pin_btn = ctk.CTkButton(top, text="📌" if self._ontop else "📍",
            width=30, height=24,
            fg_color=BG3 if self._ontop else "transparent",
            hover_color=BG3, font=ctk.CTkFont(size=11),
            text_color=NEON_CYAN if self._ontop else TEXT2,
            border_width=1, border_color=NEON_CYAN if self._ontop else LINE,
            corner_radius=4, command=self._toggle_pin)
        self._pin_btn.place(x=285, rely=0.5, anchor="center")

    def _build_body(self):
        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # 铺满整个 body
        card = ctk.CTkFrame(body, fg_color=BG2, corner_radius=0,
                             border_width=0)
        card.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        # 顶部发光条
        ctk.CTkFrame(card, fg_color=NEON_CYAN, height=2,
                     corner_radius=0).grid(row=0, column=0, sticky="ew")

        # 标题行
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 0))
        row1.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row1, text="● 账户余额",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=NEON_CYAN
            ).grid(row=0, column=0, sticky="w")

        self._bal_status = ctk.CTkLabel(row1, text="STANDBY",
            font=ctk.CTkFont(size=9, weight="bold"), text_color=TEXT3)
        self._bal_status.grid(row=0, column=1, sticky="e")

        self._bal_time = ctk.CTkLabel(row1, text="--:--",
            font=ctk.CTkFont(size=9), text_color=TEXT3)
        self._bal_time.grid(row=0, column=2, padx=(8, 0))

        # 余额大字
        self._bal_value = ctk.CTkLabel(card, text="¥ ---.--",
            font=ctk.CTkFont(size=48, weight="bold"), text_color=NEON_GREEN)
        self._bal_value.grid(row=2, column=0, sticky="nsew", padx=20, pady=(8, 10))

        # 底部发光条
        ctk.CTkFrame(card, fg_color=NEON_GREEN, height=2,
                     corner_radius=0).grid(row=3, column=0, sticky="ew")

    def _build_bot(self):
        bot = ctk.CTkFrame(self.root, fg_color=BG1, height=40, corner_radius=0)
        bot.grid(row=2, column=0, sticky="ew")
        bot.grid_propagate(False)

        # 自动刷新 — 使用按钮模拟 ON/OFF
        self._auto_btn = ctk.CTkButton(bot,
            text="自动刷新 [ ON ]" if self._auto_on else "自动刷新 [ OFF ]",
            width=90, height=24,
            fg_color=NEON_CYAN if self._auto_on else "transparent",
            hover_color=BG3,
            text_color="#000" if self._auto_on else TEXT2,
            font=ctk.CTkFont(size=9, weight="bold"),
            border_width=1, border_color=NEON_CYAN if self._auto_on else LINE,
            corner_radius=4, command=self._toggle_auto)
        self._auto_btn.place(x=8, rely=0.5, anchor="w")

        # 间隔选择
        opts = [("30秒",30),("60秒",60),("5分钟",300)]
        cur = next((l for l,v in opts if v==self._interval), "60秒")
        self._int_var = ctk.StringVar(value=cur)
        self._int_menu = ctk.CTkOptionMenu(bot, variable=self._int_var,
            values=[l for l,_ in opts],
            fg_color=BG0, button_color=NEON_CYAN, button_hover_color="#00ccdd",
            dropdown_fg_color=BG0, dropdown_hover_color=BG3,
            text_color=TEXT,
            font=ctk.CTkFont(size=9, weight="bold"), width=58, height=22,
            corner_radius=3, command=self._chg_int)
        self._int_menu.place(x=110, rely=0.5, anchor="w")

        # 状态信息
        self._sync_info = ctk.CTkLabel(bot, text="",
            font=ctk.CTkFont(size=8), text_color=NEON_GREEN)
        self._sync_info.place(x=178, rely=0.5, anchor="w")

        ctk.CTkLabel(bot, text="NEXUS v2.0",
            font=ctk.CTkFont(size=7), text_color=TEXT3
            ).place(x=290, rely=0.5, anchor="e")

    def _open_settings(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("密钥管理")
        dlg.geometry("360x240")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(fg_color=BG0)
        dlg.update_idletasks()
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"+{(sw-360)//2}+{(sh-240)//2}")

        ctk.CTkLabel(dlg, text="⚙ 密钥管理",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=NEON_CYAN
            ).pack(anchor="w", padx=14, pady=(8, 2))

        sec = ctk.CTkFrame(dlg, fg_color=BG2, corner_radius=8, border_width=1, border_color=LINE)
        sec.pack(fill="x", padx=10, pady=2)
        sec.grid_columnconfigure(1, weight=1)

        self._entry = ctk.CTkEntry(sec, placeholder_text="sk-...", height=28,
                                    fg_color=BG1, border_color=LINE)
        self._entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(6, 4))

        ctk.CTkButton(sec, text="＋ 添加", command=self._add_key_dlg,
                       fg_color=NEON_CYAN, hover_color="#00ccdd",
                       text_color="#000", height=22,
                       font=ctk.CTkFont(size=9, weight="bold"), corner_radius=4
                       ).grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")

        self._list = ctk.CTkFrame(sec, fg_color="transparent")
        self._list.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 6))
        self._render_keys()

        ctk.CTkButton(dlg, text="关闭", command=dlg.destroy,
                       fg_color=BG3, hover_color=BG2,
                       height=24, font=ctk.CTkFont(size=9)
                       ).pack(pady=6)

    def _render_keys(self):
        for w in self._list.winfo_children(): w.destroy()
        if not self.keys:
            ctk.CTkLabel(self._list, text="  (暂无密钥)",
                         font=ctk.CTkFont(size=8), text_color=TEXT3).pack(pady=4, anchor="w")
            return
        for k in self.keys:
            row = ctk.CTkFrame(self._list, fg_color="transparent")
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=mask_key(k), font=ctk.CTkFont(size=8),
                         text_color=TEXT2, anchor="w").grid(row=0, column=1, sticky="w")
            ctk.CTkButton(row, text="✕", width=20, height=16,
                           fg_color="transparent", hover_color=NEON_RED,
                           font=ctk.CTkFont(size=7), corner_radius=3,
                           command=lambda k=k: self._del_key_dlg(k)
                           ).grid(row=0, column=2, padx=(4, 0))

    def _add_key_dlg(self):
        k = self._entry.get().strip()
        if not k or not k.startswith("sk-"): return
        if k in self.keys: return
        self.keys.append(k)
        save_keys(self.keys)
        self._entry.delete(0, "end")
        if not self._sel: self._sel = k
        self._render_keys()
        self._query_bal(self._sel)

    def _del_key_dlg(self, k):
        self.keys = [x for x in self.keys if x != k]
        save_keys(self.keys)
        if self._sel == k:
            self._sel = self.keys[0] if self.keys else None
        self._render_keys()
        if self._sel: self._query_bal(self._sel)

    def _refresh_all(self):
        if self._sel: self._query_bal(self._sel)
        elif self.keys:
            self._sel = self.keys[0]; self._query_bal(self._sel)

    def _query_bal(self, key):
        if self._busy: return
        self._busy = True
        self._bal_status.configure(text="SCAN")

        def run():
            try:
                r = requests.get(API_BALANCE,
                    headers={"Authorization": f"Bearer {key}"}, timeout=15)
                d = r.json()
                self._bal[key] = d
                self.root.after(0, lambda: self._show_bal(d))
            except:
                self.root.after(0, lambda: self._show_bal_err())
            finally:
                self._busy = False

        threading.Thread(target=run, daemon=True).start()

    def _show_bal(self, d):
        if "balance_infos" not in d: return
        info = d["balance_infos"][0]
        total = float(info.get("total_balance", 0))
        ok = d.get("is_available", True)
        self._bal_value.configure(text=fmt(total))
        self._bal_time.configure(text=datetime.now().strftime("%H:%M"))
        clr = NEON_GREEN if ok else NEON_RED
        self._bal_status.configure(text="ACTIVE" if ok else "DOWN", text_color=clr)

    def _show_bal_err(self):
        self._bal_value.configure(text="⚠ ---")
        self._bal_status.configure(text="ERR", text_color=NEON_RED)
        self._bal_time.configure(text=datetime.now().strftime("%H:%M"))

    def _start(self):
        if self._sel: self._query_bal(self._sel)
        elif self.keys:
            self._sel = self.keys[0]; self._query_bal(self._sel)
        self._schedule()

    def _schedule(self):
        if self._timer: self.root.after_cancel(self._timer); self._timer = None
        if not self._auto_on: return
        self._timer = self.root.after(self._interval * 1000, self._tick)

    def _tick(self):
        if not self._auto_on: return
        if not self._busy:
            if self._sel: self._query_bal(self._sel)
            elif self.keys:
                self._sel = self.keys[0]; self._query_bal(self._sel)
        self._schedule()

    def _toggle_auto(self):
        self._auto_on = not self._auto_on
        self.cfg["auto_refresh"] = self._auto_on
        save_cfg(self.cfg)
        self._update_auto_btn()
        if self._auto_on:
            self._schedule()
            self._sync_info.configure(text="AUTO · 运行中")
        else:
            if self._timer: self.root.after_cancel(self._timer); self._timer = None
            self._sync_info.configure(text="")

    def _update_auto_btn(self):
        self._auto_btn.configure(
            text="自动刷新 [ ON ]" if self._auto_on else "自动刷新 [ OFF ]",
            fg_color=NEON_CYAN if self._auto_on else "transparent",
            text_color="#000" if self._auto_on else TEXT2,
            border_color=NEON_CYAN if self._auto_on else LINE)

    def _chg_int(self, c):
        m = {"30秒":30, "60秒":60, "5分钟":300}
        self._interval = m.get(c, 60)
        self.cfg["interval"] = self._interval
        save_cfg(self.cfg)
        if self._auto_on: self._schedule()

    def _toggle_pin(self):
        self._ontop = not self._ontop
        self.root.attributes("-topmost", self._ontop)
        self.cfg["ontop"] = self._ontop
        save_cfg(self.cfg)
        self._pin_btn.configure(text="📌" if self._ontop else "📍",
            text_color=NEON_CYAN if self._ontop else TEXT2,
            fg_color=BG3 if self._ontop else "transparent",
            border_color=NEON_CYAN if self._ontop else LINE)

    def run(self):
        self.root.mainloop()
