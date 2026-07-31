# -*- coding: utf-8 -*-
"""
摄影采集 PhotoScraper · 桌面版
现代化 GUI · 三个摄影网站高清图片采集 · 定时自动更新
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu
import os, sys, json, threading, webbrowser
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw
import photo_scraper

DEF_CFG = {
    "save_dir": os.path.join(os.path.expanduser("~"), "Pictures", "PhotoScraper"),
    "interval_h": 5, "cnu_enabled": True, "500px_enabled": True, "dili_enabled": True,
    "cnu_pages": 2, "500px_pages": 2, "max_gb": 5, "thumb_size": 220, "last_update": "",
}
CFG_FILE = "photoscaper_cfg.json"
HIST_FILE = "photoscaper_hist.json"

THUMB_CACHE = {}

def load_cfg():
    if os.path.exists(CFG_FILE):
        try:
            c = json.load(open(CFG_FILE, "r", encoding="utf-8"))
            for k, v in DEF_CFG.items(): c.setdefault(k, v)
            return c
        except: pass
    return dict(DEF_CFG)

def save_cfg(c): json.dump(c, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
def load_hist():
    if os.path.exists(HIST_FILE):
        try: return json.load(open(HIST_FILE, "r", encoding="utf-8"))
        except: pass
    return []
def save_hist(h): json.dump(h, open(HIST_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def rel_time(ts):
    if not ts: return ""
    try:
        dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
        d = datetime.now() - dt
        if d < timedelta(minutes=1): return "刚刚"
        if d < timedelta(hours=1): return f"{d.seconds//60}m"
        if d < timedelta(days=1): return f"{d.seconds//3600}h"
        if d.days < 7: return f"{d.days}d"
        return dt.strftime("%m-%d")
    except: return ""

def fmt_time(ts):
    if not ts: return "从未"
    try:
        dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
        return dt.strftime("%Y-%m-%d %H:%M")
    except: return str(ts)[:16]

def get_thumb(fp, size=220):
    if fp in THUMB_CACHE: return THUMB_CACHE[fp]
    try:
        if os.path.exists(fp):
            img = Image.open(fp).convert("RGB")
        else:
            img = Image.new("RGB", (size, size), (48, 48, 48))
    except:
        img = Image.new("RGB", (size, size), (48, 48, 48))
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (235, 236, 240))
    w, h = img.size
    canvas.paste(img, ((size - w) // 2, (size - h) // 2))
    tk_img = ImageTk.PhotoImage(canvas)
    THUMB_CACHE[fp] = tk_img
    return tk_img

# ─── 预览窗口 ─────────────────────
class Preview(tk.Toplevel):
    def __init__(self, master, item, hist, filt, refresh_cb):
        super().__init__(master)
        self.item, self.hist, self.filter, self.refresh_cb = item, hist, filt, refresh_cb
        self.title(item.get("title", "预览"))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.85), int(sh * 0.85)
        self.geometry(f"{w}x{h}+{sw//2-w//2}+{sh//2-h//2}")
        self.configure(bg="#111")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Left>", lambda e: self.nav(-1))
        self.bind("<Right>", lambda e: self.nav(1))

        bar = tk.Frame(self, bg="#1a1a1a", height=48)
        bar.pack(side=tk.BOTTOM, fill=tk.X); bar.pack_propagate(False)
        info = f"  {item.get('title','')[:40]}  ·  {item.get('author','')}  ·  {item.get('site','')}"
        tk.Label(bar, text=info, fg="#ccc", bg="#1a1a1a", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=14, pady=12)
        bs = dict(bg="#2a2a2a", fg="#ddd", relief=tk.FLAT, font=("Microsoft YaHei UI", 9), cursor="hand2", padx=14, pady=5)
        tk.Button(bar, text="🌐 网页", command=lambda: webbrowser.open(item.get("page_url","")) if item.get("page_url") else None, **bs).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="📁 文件夹", command=lambda: os.startfile(os.path.dirname(item.get("filepath",""))) if item.get("filepath") and os.path.exists(item.get("filepath")) else None, **bs).pack(side=tk.RIGHT, padx=3)
        def do_del():
            if messagebox.askyesno("确认", "删除？"):
                fp = item.get("filepath", "");
                if fp and os.path.exists(fp):
                    try: os.remove(fp)
                    except: pass
                if item in self.hist: self.hist.remove(item)
                save_hist(self.hist); THUMB_CACHE.pop(item.get("filepath",""), None)
                self.refresh_cb(); self.destroy()
        tk.Button(bar, text="🗑 删除", command=do_del, **bs).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="✕ 关闭", command=self.destroy, **bs).pack(side=tk.RIGHT, padx=3)

        self.canvas = tk.Canvas(self, bg="#111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._resize())
        self._load()

    def _load(self):
        fp = self.item.get("filepath", "")
        self.orig = Image.open(fp).convert("RGB") if fp and os.path.exists(fp) else Image.new("RGB", (400, 300), (30, 30, 30))
        self._resize()
    def _resize(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10 or not hasattr(self, 'orig'): return
        img = self.orig.copy(); img.thumbnail((cw, ch), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all"); self.canvas.create_image(cw//2, ch//2, image=self.photo, anchor=tk.CENTER)
    def nav(self, d):
        fh = [x for x in self.hist if self.filter == "全部" or x.get("site", "") == self.filter]
        try: idx = fh.index(self.item)
        except: return
        ni = idx + d
        if 0 <= ni < len(fh):
            self.destroy(); Preview(self.master, fh[ni], self.hist, self.filter, self.refresh_cb)

# ─── 设置面板 ─────────────────────
class Settings(tk.Toplevel):
    def __init__(self, master, cfg, on_done):
        super().__init__(master)
        self.cfg = dict(cfg); self.on_done = on_done
        self.title("设置"); self.geometry("460x480"); self.resizable(False, False)
        self.configure(bg="#f8f9fa"); self.transient(master); self.grab_set()
        hdr = tk.Frame(self, bg="#4a90d9", height=42)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  设 置", fg="white", bg="#4a90d9", font=("Microsoft YaHei UI", 13, "bold")).pack(side=tk.LEFT, padx=18, pady=9)
        m = tk.Frame(self, bg="#f8f9fa", padx=22, pady=16); m.pack(fill=tk.BOTH, expand=True)
        ls = dict(font=("Microsoft YaHei UI", 10), bg="#f8f9fa", anchor="w", fg="#333")
        tk.Label(m, text="图片保存目录", **ls).grid(row=0, column=0, sticky="w", pady=(4, 2))
        df = tk.Frame(m, bg="#f8f9fa"); df.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.dir_var = tk.StringVar(value=cfg["save_dir"])
        tk.Entry(df, textvariable=self.dir_var, font=("Consolas", 9), width=38, bd=1, relief=tk.GROOVE).pack(side=tk.LEFT)
        tk.Button(df, text="📂", font=("", 12), bg="#fff", bd=0, cursor="hand2",
                  command=lambda: self.dir_var.set(filedialog.askdirectory(title="选择目录") or self.dir_var.get())).pack(side=tk.LEFT, padx=4)
        r = 2
        self.iv = tk.IntVar(value=cfg["interval_h"])
        self.sv = tk.IntVar(value=cfg["max_gb"])
        for var, label, fr, to in [(self.iv, "更新间隔（小时）", 1, 24), (self.sv, "最大存储（GB）", 1, 50)]:
            tk.Label(m, text=label, **ls).grid(row=r, column=0, sticky="w", pady=(8, 2)); r += 1
            tk.Scale(m, from_=fr, to=to, orient=tk.HORIZONTAL, variable=var, bg="#f8f9fa", length=300,
                     troughcolor="#ddd", highlightthickness=0).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        tk.Label(m, text="抓取页数", **ls).grid(row=r, column=0, sticky="w", pady=(8, 2)); r += 1
        pf = tk.Frame(m, bg="#f8f9fa"); pf.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, 10)); r += 1
        tk.Label(pf, text="CNU:", bg="#f8f9fa", font=("", 9)).pack(side=tk.LEFT)
        self.cp = tk.IntVar(value=cfg["cnu_pages"]); tk.Spinbox(pf, from_=1, to=10, textvariable=self.cp, width=4, font=("", 10)).pack(side=tk.LEFT, padx=(4, 14))
        tk.Label(pf, text="500px:", bg="#f8f9fa", font=("", 9)).pack(side=tk.LEFT)
        self.pp = tk.IntVar(value=cfg["500px_pages"]); tk.Spinbox(pf, from_=1, to=10, textvariable=self.pp, width=4, font=("", 10)).pack(side=tk.LEFT, padx=4)
        self.ce = tk.BooleanVar(value=cfg["cnu_enabled"]); self.pe = tk.BooleanVar(value=cfg["500px_enabled"]); self.de = tk.BooleanVar(value=cfg["dili_enabled"])
        for var, label in [(self.ce, "CNU 视觉联盟"), (self.pe, "500px 摄影社区"), (self.de, "中国国家地理")]:
            tk.Checkbutton(m, text=label, variable=var, bg="#f8f9fa", font=("Microsoft YaHei UI", 10), fg="#444",
                           activebackground="#f0f0f0", selectcolor="#f8f9fa").grid(row=r, column=0, sticky="w", pady=2); r += 1
        r += 1
        bf = tk.Frame(m, bg="#f8f9fa"); bf.grid(row=r, column=0, columnspan=2, sticky="e", pady=(10, 0))
        tk.Button(bf, text="取消", command=self.destroy, font=("Microsoft YaHei UI", 10), bg="#e0e0e0", fg="#333",
                  relief=tk.FLAT, padx=20, pady=6, cursor="hand2").pack(side=tk.RIGHT, padx=6)
        tk.Button(bf, text="保存设置", command=self._save, font=("Microsoft YaHei UI", 10, "bold"), bg="#4a90d9", fg="white",
                  relief=tk.FLAT, padx=20, pady=6, cursor="hand2").pack(side=tk.RIGHT)

    def _save(self):
        self.cfg["save_dir"] = self.dir_var.get(); self.cfg["interval_h"] = self.iv.get()
        self.cfg["max_gb"] = self.sv.get(); self.cfg["cnu_pages"] = self.cp.get()
        self.cfg["500px_pages"] = self.pp.get(); self.cfg["cnu_enabled"] = self.ce.get()
        self.cfg["500px_enabled"] = self.pe.get(); self.cfg["dili_enabled"] = self.de.get()
        save_cfg(self.cfg); self.on_done(self.cfg); self.destroy()

# ─── 主应用 ───────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg(); self.hist = load_hist()
        self.filt = "全部"; self.running = False; self.job_id = None
        os.makedirs(self.cfg["save_dir"], exist_ok=True)
        self._ui(); self._sync(); self._show(); self._sched()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.minsize(820, 520)

    def _ui(self):
        self.root.title("摄影采集")
        self.root.geometry("1150x700"); self.root.configure(bg="#f2f2f7")
        top = tk.Frame(self.root, bg="white", height=52); top.pack(fill=tk.X); top.pack_propagate(False)
        tk.Label(top, text="📷", font=("", 20), bg="white").pack(side=tk.LEFT, padx=(14, 4), pady=9)
        tk.Label(top, text="摄影采集", font=("Microsoft YaHei UI", 14, "bold"), fg="#222", bg="white").pack(side=tk.LEFT, pady=12)
        ttk.Separator(top, orient="vertical").pack(side=tk.LEFT, padx=12, fill="y")
        self.status_lbl = tk.Label(top, text="就绪", font=("Microsoft YaHei UI", 9), fg="#999", bg="white")
        self.status_lbl.pack(side=tk.LEFT, pady=16)

        frm = tk.Frame(top, bg="white"); frm.pack(side=tk.LEFT, padx=(28, 0), pady=9)
        self.fb = {}
        for s in ["全部", "CNU视觉联盟", "500px摄影社区", "中国国家地理"]:
            b = tk.Label(frm, text=s, font=("Microsoft YaHei UI", 9), fg="#666", bg="#f5f5f7", padx=12, pady=5, cursor="hand2")
            b.pack(side=tk.LEFT, padx=2); b.bind("<Button-1>", lambda e, st=s: self._filt(st)); self.fb[s] = b
        self._hf()

        rf = tk.Frame(top, bg="white"); rf.pack(side=tk.RIGHT, padx=10, pady=7)
        bb = dict(font=("Microsoft YaHei UI", 9), relief=tk.FLAT, padx=16, pady=6, cursor="hand2")
        self.fetch_btn = tk.Button(rf, text="🔄 开始采集", command=self._go, bg="#4a90d9", fg="white", activebackground="#357abd", activeforeground="white", **bb)
        self.fetch_btn.pack(side=tk.LEFT, padx=3)
        tk.Button(rf, text="📁", command=self._odir, bg="#eee", fg="#555", **bb).pack(side=tk.LEFT, padx=3)
        tk.Button(rf, text="⚙", command=self._stg, bg="#eee", fg="#555", **bb).pack(side=tk.LEFT, padx=3)

        main = tk.Frame(self.root, bg="#f2f2f7"); main.pack(fill=tk.BOTH, expand=True, padx=0, pady=1)
        self.canvas = tk.Canvas(main, bg="#f2f2f7", highlightthickness=0)
        vbar = tk.Scrollbar(main, orient="vertical", command=self.canvas.yview, width=8)
        self.gw = tk.Frame(self.canvas, bg="#f2f2f7")
        self.gw.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.gw, anchor="nw")
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas.find_all()[0], width=e.width) if self.canvas.find_all() else None)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.gf = tk.Frame(self.gw, bg="#f2f2f7", padx=18, pady=18); self.gf.pack()

        bar = tk.Frame(self.root, bg="#1e1e24", height=28); bar.pack(fill=tk.X, side=tk.BOTTOM); bar.pack_propagate(False)
        self.stats_var = tk.StringVar(value=""); self.next_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.stats_var, fg="#909090", bg="#1e1e24", font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=14, pady=4)
        tk.Label(bar, textvariable=self.next_var, fg="#909090", bg="#1e1e24", font=("Microsoft YaHei UI", 8)).pack(side=tk.RIGHT, padx=14, pady=4)

    def _filt(self, s): self.filt = s; self._hf(); self._show()
    def _hf(self):
        for s, b in self.fb.items(): b.configure(fg="white" if s == self.filt else "#666", bg="#4a90d9" if s == self.filt else "#f5f5f7")
    def _odir(self): d = self.cfg["save_dir"]; os.startfile(d) if d and os.path.exists(d) else messagebox.showinfo("提示", "目录不存在")

    def _sync(self):
        exist = {h.get("filepath", "") for h in self.hist}
        for root, dirs, files in os.walk(self.cfg["save_dir"]):
            for f in files:
                if not f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')): continue
                fp = os.path.join(root, f)
                if fp in exist: continue
                site = "未知"
                if "cnu" in f.lower(): site = "CNU视觉联盟"
                elif "500px" in f.lower(): site = "500px摄影社区"
                elif "dili" in f.lower(): site = "中国国家地理"
                self.hist.append(dict(id=f"disk_{hash(fp)}", title=os.path.splitext(f)[0], author="", site=site,
                                      filepath=fp, size=os.path.getsize(fp), page_url="",
                                      date=datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d"), category=""))
                exist.add(fp)
        save_hist(self.hist)

    def _show(self):
        for w in self.gf.winfo_children(): w.destroy()
        items = self.hist if self.filt == "全部" else [h for h in self.hist if h.get("site") == self.filt]
        if not items:
            tk.Label(self.gf, text="✨ 点击「开始采集」获取精美摄影作品\n\n支持: CNU视觉联盟 · 500px摄影社区 · 中国国家地理",
                     font=("Microsoft YaHei UI", 13), fg="#bbb", bg="#f2f2f7", justify="center").pack(expand=True, pady=80)
            self._stats(items); return
        ts = self.cfg.get("thumb_size", 220); cw = self.canvas.winfo_width()
        if cw < 200: cw = 1000
        cols = max(2, (cw - 36) // (ts + 24))
        sc = {"CNU视觉联盟": "#e74c3c", "500px摄影社区": "#f5a623", "中国国家地理": "#2ecc71"}
        r, c = 0, 0
        for item in items:
            card = tk.Frame(self.gf, bg="white", padx=0, pady=0, highlightthickness=0, cursor="hand2")
            card.grid(row=r, column=c, padx=8, pady=8, sticky="n")
            fp = item.get("filepath", ""); thumb = get_thumb(fp, ts)
            img = tk.Label(card, image=thumb, bg="#e8e8ec", cursor="hand2", bd=0); img.image = thumb; img.pack()
            info = tk.Frame(card, bg="white", padx=8, pady=6); info.pack(fill=tk.X)
            tk.Label(info, text=item.get("title", "无标题")[:18], font=("Microsoft YaHei UI", 9, "bold"), fg="#2c2c2c", bg="white", anchor="w").pack(fill=tk.X)
            sub = tk.Frame(info, bg="white"); sub.pack(fill=tk.X, pady=(3, 0))
            s = item.get("site", ""); tk.Label(sub, text=s, font=("Microsoft YaHei UI", 7), fg=sc.get(s, "#888"), bg="white").pack(side=tk.LEFT)
            tk.Label(sub, text=rel_time(item.get("date", "")), font=("Microsoft YaHei UI", 7), fg="#aaa", bg="white").pack(side=tk.RIGHT)
            for w in [card, img, info, sub]: w.bind("<Button-1>", lambda e, it=item: self._pv(it))
            card.bind("<Button-3>", lambda e, it=item: self._ctx(e, it)); img.bind("<Button-3>", lambda e, it=item: self._ctx(e, it))
            c += 1
            if c >= cols: c = 0; r += 1
        self._stats(items)

    def _pv(self, it): Preview(self.root, it, self.hist, self.filt, self._show)
    def _ctx(self, e, it):
        m = Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 9))
        m.add_command(label="🔍 预览", command=lambda: self._pv(it))
        m.add_command(label="📁 打开位置", command=lambda: os.startfile(os.path.dirname(it.get("filepath", ""))) if it.get("filepath") and os.path.exists(it.get("filepath")) else None)
        m.add_command(label="🗑 删除", command=lambda: self._del(it)); m.post(e.x_root, e.y_root)
    def _del(self, it):
        if messagebox.askyesno("确认", "删除？"):
            fp = it.get("filepath", "")
            if fp and os.path.exists(fp):
                try: os.remove(fp)
                except: pass
            if it in self.hist: self.hist.remove(it)
            save_hist(self.hist); THUMB_CACHE.pop(it.get("filepath", ""), None); self._show()

    def _stats(self, items=None):
        if items is None: items = self.hist if self.filt == "全部" else [h for h in self.hist if h.get("site") == self.filt]
        total, bs, ts = len(self.hist), {}, 0
        for h in self.hist:
            s = h.get("site", "未知"); bs[s] = bs.get(s, 0) + 1; ts += h.get("size", 0) / (1024 * 1024)
        lu = fmt_time(self.cfg.get("last_update", ""))
        self.stats_var.set(f"共 {total} 张 | {' · '.join(f'{k}: {v}' for k, v in bs.items())} | {ts:.0f} MB | 更新: {lu}")
        self.root.title(f"摄影采集 — {len(items)} 张")

    def _go(self):
        if self.running: return
        threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        self.running = True
        self.root.after(0, lambda: self.fetch_btn.configure(text="⏳ 采集中...", state=tk.DISABLED))
        self.root.after(0, lambda: self.status_lbl.configure(text="正在采集...", fg="#f5a623"))
        exist = {h.get("id", "") for h in self.hist}
        new_r = photo_scraper.run_scrape_all(self.cfg)
        added = 0
        for r in new_r:
            if r["id"] not in exist:
                self.hist.append(r); exist.add(r["id"]); added += 1
        # cleanup
        max_b = self.cfg.get("max_gb", 5) * 1024**3
        base = self.cfg["save_dir"]
        if os.path.exists(base):
            files = []
            total_s = 0
            for root, dirs, fnames in os.walk(base):
                for fn in fnames:
                    fp = os.path.join(root, fn); sz = os.path.getsize(fp)
                    files.append((fp, sz, os.path.getmtime(fp))); total_s += sz
            if total_s > max_b:
                files.sort(key=lambda x: x[2])
                for fp, sz, _ in files:
                    if total_s <= max_b * 0.75: break
                    try: os.remove(fp); total_s -= sz
                    except: pass
        self.cfg["last_update"] = datetime.now().isoformat()
        save_cfg(self.cfg); save_hist(self.hist)
        self.running = False
        self.root.after(0, lambda: self.fetch_btn.configure(text="🔄 开始采集", state=tk.NORMAL))
        self.root.after(0, lambda: self.status_lbl.configure(text=f"完成 — 新增 {added} 张", fg="#2ecc71"))
        self.root.after(0, self._show); self.root.after(0, self._sched)

    def _sched(self):
        if self.job_id: self.root.after_cancel(self.job_id)
        ms = self.cfg.get("interval_h", 5) * 3600 * 1000
        self.job_id = self.root.after(ms, self._auto)
        nt = datetime.now() + timedelta(milliseconds=ms)
        self.next_var.set(f"下次: {nt.strftime('%H:%M')} (间隔 {self.cfg['interval_h']}h)")
    def _auto(self):
        if not self.running:
            self.root.after(0, lambda: self.status_lbl.configure(text="⏰ 定时触发...", fg="#4a90d9"))
            threading.Thread(target=self._run, daemon=True).start()
    def _stg(self):
        def done(cfg): self.cfg = cfg; self._sched()
        Settings(self.root, self.cfg, done)
    def _close(self):
        save_hist(self.hist); self.root.destroy()

def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    root = tk.Tk(); App(root); root.mainloop()

if __name__ == "__main__": main()
