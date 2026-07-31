"""
摄影网站图片采集桌面应用 - 主程序
支持网站: 中国国家地理网、CNU视觉联盟、500px摄影社区
使用 Tkinter 构建 GUI，支持系统托盘、定时更新、缩略图浏览
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import time
import threading
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import re
import shutil

# 导入爬虫模块
from scrapers import scrape_all

# ============================================================
# 配置管理
# ============================================================
CONFIG_FILE = "config.json"
HISTORY_FILE = "images_history.json"

DEFAULT_CONFIG = {
    "save_dir": os.path.join(os.path.expanduser("~"), "Pictures", "摄影采集"),
    "update_interval_hours": 5,
    "cnu_enabled": True,
    "500px_enabled": True,
    "dili_enabled": True,
    "cnu_pages": 3,
    "500px_pages": 3,
    "auto_startup": False,
    "max_storage_gb": 5,
    "thumbnail_size": 200,
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
        except:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_history(hist):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

# ============================================================
# 工具函数
# ============================================================
def format_time(ts_str):
    if not ts_str:
        return "从未更新"
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts_str

def get_file_size_mb(filepath):
    if os.path.exists(filepath):
        return os.path.getsize(filepath) / (1024 * 1024)
    return 0

def check_storage_limit(cfg):
    """检查存储容量，超出则清理旧图片"""
    max_bytes = cfg.get("max_storage_gb", 5) * 1024 * 1024 * 1024
    save_dir = cfg.get("save_dir", "")
    if not os.path.exists(save_dir):
        return

    total = 0
    files = []
    for root, dirs, filenames in os.walk(save_dir):
        for f in filenames:
            fp = os.path.join(root, f)
            size = os.path.getsize(fp)
            files.append((fp, size, os.path.getmtime(fp)))
            total += size

    if total > max_bytes:
        files.sort(key=lambda x: x[2])  # 按修改时间排序，旧的在前
        for fp, size, _ in files:
            if total <= max_bytes * 0.8:
                break
            try:
                os.remove(fp)
                total -= size
            except:
                pass

def make_thumbnail(filepath, size=200):
    """生成缩略图"""
    try:
        img = Image.open(filepath)
        img = img.convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        # 返回占位图
        placeholder = Image.new("RGB", (size, size), (60, 60, 60))
        draw = ImageDraw.Draw(placeholder)
        draw.text((size//2-20, size//2-8), "?", fill=(150, 150, 150))
        return ImageTk.PhotoImage(placeholder)

def get_relative_time(timestamp_str):
    """将时间戳转为相对时间描述"""
    if not timestamp_str:
        return "未知"
    try:
        dt = datetime.fromisoformat(timestamp_str)
    except:
        return timestamp_str

    diff = datetime.now() - dt
    if diff < timedelta(minutes=1):
        return "刚刚"
    elif diff < timedelta(hours=1):
        return f"{diff.seconds // 60}分钟前"
    elif diff < timedelta(days=1):
        return f"{diff.seconds // 3600}小时前"
    elif diff < timedelta(days=7):
        return f"{diff.days}天前"
    else:
        return dt.strftime("%m-%d %H:%M")

# ============================================================
# 图片预览窗口
# ============================================================
class ImagePreviewWindow(tk.Toplevel):
    """全屏/大图预览窗口"""
    def __init__(self, parent, image_data):
        super().__init__(parent)
        self.title(image_data.get("title", "图片预览"))
        self.image_data = image_data
        self.zoom_level = 0  # 0=适应窗口, 1=100%

        # 窗口设置
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = int(sw * 0.85), int(sh * 0.85)
        self.geometry(f"{w}x{h}+{sw//2-w//2}+{sh//2-h//2}")
        self.configure(bg="#1a1a1a")

        # 绑定事件
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Left>", lambda e: self.navigate(-1))
        self.bind("<Right>", lambda e: self.navigate(1))
        self.bind("<Button-3>", lambda e: self.destroy())  # 右键关闭

        self._build_ui()
        self._load_image()

    def _build_ui(self):
        # 底部信息栏
        info_frame = tk.Frame(self, bg="#2d2d2d", height=60)
        info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        info_frame.pack_propagate(False)

        info_text = f"{self.image_data.get('title', '无标题')}  |  {self.image_data.get('author', '未知作者')}  |  {self.image_data.get('site', '')}  |  {self.image_data.get('date', '')}"
        info_label = tk.Label(info_frame, text=info_text, fg="#aaa", bg="#2d2d2d",
                              font=("Microsoft YaHei UI", 10))
        info_label.pack(side=tk.LEFT, padx=15, pady=18)

        # 按钮
        btn_frame = tk.Frame(info_frame, bg="#2d2d2d")
        btn_frame.pack(side=tk.RIGHT, padx=10, pady=12)

        btn_style = {"bg": "#3d3d3d", "fg": "#ddd", "relief": tk.FLAT, "font": ("Microsoft YaHei UI", 9),
                     "cursor": "hand2", "padx": 12, "pady": 4}

        def open_in_browser():
            url = self.image_data.get("page_url", "")
            if url:
                import webbrowser
                webbrowser.open(url)

        def open_folder():
            fp = self.image_data.get("filepath", "")
            if fp and os.path.exists(fp):
                os.startfile(os.path.dirname(fp))

        tk.Button(btn_frame, text="🌐 在浏览器打开", command=open_in_browser, **btn_style).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="📁 打开文件夹", command=open_folder, **btn_style).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="✕ 关闭", command=self.destroy, **btn_style).pack(side=tk.LEFT, padx=4)

        # 图片显示区域
        self.canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._resize_image())

    def _load_image(self):
        fp = self.image_data.get("filepath", "")
        if not os.path.exists(fp):
            self.canvas.create_text(400, 300, text="图片文件不存在", fill="#888", font=("", 16))
            return
        self.original_image = Image.open(fp)
        self.original_image = self.original_image.convert("RGB")
        self._resize_image()

    def _resize_image(self):
        if not hasattr(self, 'original_image'):
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        img = self.original_image.copy()
        img.thumbnail((cw, ch), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.photo, anchor=tk.CENTER)

    def navigate(self, direction):
        """导航到上一张/下一张"""
        # 通过 parent 调用
        if hasattr(self.master, 'navigate_preview'):
            self.master.navigate_preview(direction, self.image_data)
            self.destroy()

# ============================================================
# 设置面板窗口
# ============================================================
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, config, on_save):
        super().__init__(parent)
        self.title("设置")
        self.config = config
        self.on_save = on_save
        self.result = dict(config)

        self.geometry("500x520")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.focus_set()

    def _build_ui(self):
        # 标题
        header = tk.Frame(self, bg="#2d7fd9", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="⚙ 设置", fg="white", bg="#2d7fd9",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(side=tk.LEFT, padx=20, pady=12)

        # 内容区域
        main = tk.Frame(self, bg="#f5f5f5", padx=20, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        row_style = {"bg": "#f5f5f5"}
        label_style = {"font": ("Microsoft YaHei UI", 10), "bg": "#f5f5f5", "anchor": "w"}

        row = 0

        # --- 保存目录 ---
        tk.Label(main, text="图片保存目录:", **label_style).grid(row=row, column=0, sticky="w", pady=(15, 5))
        dir_frame = tk.Frame(main, bg="#f5f5f5")
        dir_frame.grid(row=row+1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.dir_var = tk.StringVar(value=self.config.get("save_dir", ""))
        dir_entry = tk.Entry(dir_frame, textvariable=self.dir_var, font=("", 9), width=45)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(dir_frame, text="浏览...", command=self._browse_dir,
                  font=("", 9), bg="#fff", relief=tk.GROOVE, cursor="hand2").pack(side=tk.LEFT, padx=(5, 0))
        row += 2

        # --- 更新间隔 ---
        tk.Label(main, text="自动更新间隔:", **label_style).grid(row=row, column=0, sticky="w", pady=5)
        self.interval_var = tk.IntVar(value=self.config.get("update_interval_hours", 5))
        interval_frame = tk.Frame(main, bg="#f5f5f5")
        interval_frame.grid(row=row, column=1, sticky="w", pady=5)
        tk.Spinbox(interval_frame, from_=1, to=24, textvariable=self.interval_var, width=4,
                   font=("", 10)).pack(side=tk.LEFT)
        tk.Label(interval_frame, text="小时", bg="#f5f5f5", font=("", 9)).pack(side=tk.LEFT, padx=(5, 0))
        row += 1

        # --- 最大存储 ---
        tk.Label(main, text="最大存储容量:", **label_style).grid(row=row, column=0, sticky="w", pady=5)
        self.storage_var = tk.IntVar(value=self.config.get("max_storage_gb", 5))
        storage_frame = tk.Frame(main, bg="#f5f5f5")
        storage_frame.grid(row=row, column=1, sticky="w", pady=5)
        tk.Spinbox(storage_frame, from_=1, to=50, textvariable=self.storage_var, width=4,
                   font=("", 10)).pack(side=tk.LEFT)
        tk.Label(storage_frame, text="GB", bg="#f5f5f5", font=("", 9)).pack(side=tk.LEFT, padx=(5, 0))
        row += 1

        # --- 缩略图大小 ---
        tk.Label(main, text="缩略图大小:", **label_style).grid(row=row, column=0, sticky="w", pady=5)
        self.thumb_var = tk.IntVar(value=self.config.get("thumbnail_size", 200))
        thumb_frame = tk.Frame(main, bg="#f5f5f5")
        thumb_frame.grid(row=row, column=1, sticky="w", pady=5)
        tk.Radiobutton(thumb_frame, text="小", variable=self.thumb_var, value=150, bg="#f5f5f5").pack(side=tk.LEFT)
        tk.Radiobutton(thumb_frame, text="中", variable=self.thumb_var, value=200, bg="#f5f5f5").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(thumb_frame, text="大", variable=self.thumb_var, value=280, bg="#f5f5f5").pack(side=tk.LEFT)
        row += 1

        # --- 分割线 ---
        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=15)
        row += 1

        # --- 爬虫页数 ---
        tk.Label(main, text="CNU 抓取页数:", **label_style).grid(row=row, column=0, sticky="w", pady=5)
        self.cnu_pages_var = tk.IntVar(value=self.config.get("cnu_pages", 3))
        tk.Spinbox(main, from_=1, to=10, textvariable=self.cnu_pages_var, width=4,
                   font=("", 10)).grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        tk.Label(main, text="500px 抓取页数:", **label_style).grid(row=row, column=0, sticky="w", pady=5)
        self.px500_pages_var = tk.IntVar(value=self.config.get("500px_pages", 3))
        tk.Spinbox(main, from_=1, to=10, textvariable=self.px500_pages_var, width=4,
                   font=("", 10)).grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- 分割线 ---
        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=15)
        row += 1

        # --- 启用开关 ---
        self.cnu_enabled = tk.BooleanVar(value=self.config.get("cnu_enabled", True))
        self.px500_enabled = tk.BooleanVar(value=self.config.get("500px_enabled", True))
        self.dili_enabled = tk.BooleanVar(value=self.config.get("dili_enabled", True))
        self.startup_var = tk.BooleanVar(value=self.config.get("auto_startup", False))

        tk.Checkbutton(main, text="启用 CNU视觉联盟", variable=self.cnu_enabled, bg="#f5f5f5",
                       font=("", 9)).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1
        tk.Checkbutton(main, text="启用 500px摄影社区", variable=self.px500_enabled, bg="#f5f5f5",
                       font=("", 9)).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1
        tk.Checkbutton(main, text="启用 中国国家地理", variable=self.dili_enabled, bg="#f5f5f5",
                       font=("", 9)).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1
        tk.Checkbutton(main, text="开机自启动", variable=self.startup_var, bg="#f5f5f5",
                       font=("", 9)).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

        # --- 按钮 ---
        btn_frame = tk.Frame(main, bg="#f5f5f5")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="e", pady=(20, 0))

        save_btn = tk.Button(btn_frame, text="保存设置", command=self._save,
                             bg="#2d7fd9", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
                             relief=tk.FLAT, padx=20, pady=6, cursor="hand2")
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_btn = tk.Button(btn_frame, text="取消", command=self.destroy,
                               bg="#ddd", fg="#333", font=("Microsoft YaHei UI", 10),
                               relief=tk.FLAT, padx=20, pady=6, cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT)

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择图片保存目录")
        if d:
            self.dir_var.set(d)

    def _save(self):
        self.result["save_dir"] = self.dir_var.get()
        self.result["update_interval_hours"] = self.interval_var.get()
        self.result["max_storage_gb"] = self.storage_var.get()
        self.result["thumbnail_size"] = self.thumb_var.get()
        self.result["cnu_pages"] = self.cnu_pages_var.get()
        self.result["500px_pages"] = self.px500_pages_var.get()
        self.result["cnu_enabled"] = self.cnu_enabled.get()
        self.result["500px_enabled"] = self.px500_enabled.get()
        self.result["dili_enabled"] = self.dili_enabled.get()
        self.result["auto_startup"] = self.startup_var.get()

        save_config(self.result)
        self.on_save(self.result)
        self.destroy()


def setup_autostart(enable):
    """设置开机自启动 (Windows)"""
    import winreg
    startup_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "PhotoScraper"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_path, 0,
                             winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if enable:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"开机启动设置失败: {e}")

# ============================================================
# 主应用窗口
# ============================================================
class PhotoScraperApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.history = load_history()
        self.thumbnails = {}  # id -> PhotoImage
        self.current_filter = "全部"
        self.is_running = False
        self.preview_window = None
        self._update_job = None

        os.makedirs(self.config.get("save_dir", "./downloads"), exist_ok=True)

        self._setup_ui()
        self._load_existing_images()
        self._schedule_next_update()

        # 如果最小化模式
        if "--minimized" in sys.argv:
            self.root.iconify()

        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        self.root.title("摄影采集 - 图片采集工具")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)
        self.root.configure(bg="#f0f0f0")

        try:
            self.root.iconbitmap(default="")
        except:
            pass

        # ====== 顶部工具栏 ======
        toolbar = tk.Frame(self.root, bg="#ffffff", height=52, relief=tk.SOLID, bd=0)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)

        # 标题
        title_frame = tk.Frame(toolbar, bg="white")
        title_frame.pack(side=tk.LEFT, padx=15, pady=8)

        tk.Label(title_frame, text="📷 摄影采集", font=("Microsoft YaHei UI", 14, "bold"),
                 fg="#2d7fd9", bg="white").pack(side=tk.LEFT)

        # 分隔线
        ttk.Separator(title_frame, orient="vertical").pack(side=tk.LEFT, padx=12, fill="y")

        self.status_label = tk.Label(title_frame, text="就绪", font=("Microsoft YaHei UI", 9),
                                     fg="#888", bg="white")
        self.status_label.pack(side=tk.LEFT)

        # 筛选按钮
        filter_frame = tk.Frame(toolbar, bg="white")
        filter_frame.pack(side=tk.LEFT, padx=(30, 0), pady=10)

        sites = ["全部", "CNU视觉联盟", "500px摄影社区", "中国国家地理"]
        self.filter_buttons = {}
        for s in sites:
            btn = tk.Label(filter_frame, text=s, font=("Microsoft YaHei UI", 9),
                           fg="#666", bg="#f5f5f5", padx=10, pady=4, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=2)
            btn.bind("<Button-1>", lambda e, site=s: self._filter_by_site(site))
            self.filter_buttons[s] = btn
        self._update_filter_highlight()

        # 右侧按钮
        right_frame = tk.Frame(toolbar, bg="white")
        right_frame.pack(side=tk.RIGHT, padx=10, pady=8)

        btn_kwargs = {
            "font": ("Microsoft YaHei UI", 9),
            "relief": tk.FLAT,
            "padx": 14,
            "pady": 6,
            "cursor": "hand2",
        }

        self.fetch_btn = tk.Button(right_frame, text="🔄 立即更新", command=self._start_fetch,
                                   bg="#2d7fd9", fg="white", activebackground="#1a6bc0",
                                   activeforeground="white", **btn_kwargs)
        self.fetch_btn.pack(side=tk.LEFT, padx=3)

        self.folder_btn = tk.Button(right_frame, text="📁 文件夹", command=self._open_save_folder,
                                    bg="#eee", fg="#333", **btn_kwargs)
        self.folder_btn.pack(side=tk.LEFT, padx=3)

        self.settings_btn = tk.Button(right_frame, text="⚙ 设置", command=self._open_settings,
                                      bg="#eee", fg="#333", **btn_kwargs)
        self.settings_btn.pack(side=tk.LEFT, padx=3)

        # ====== 主内容区 ======
        content_frame = tk.Frame(self.root, bg="#f0f0f0")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=1)

        # Canvas + Scrollbar
        self.main_canvas = tk.Canvas(content_frame, bg="#f0f0f0", highlightthickness=0)
        scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=self.main_canvas.yview)
        self.scroll_frame = tk.Frame(self.main_canvas, bg="#f0f0f0")

        self.scroll_frame.bind("<Configure>",
                               lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))

        self.canvas_window = self.main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        self.main_canvas.configure(yscrollcommand=scrollbar.set)
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 缩略图容器
        self.grid_frame = tk.Frame(self.scroll_frame, bg="#f0f0f0", padx=15, pady=15)
        self.grid_frame.pack(fill=tk.BOTH, expand=True)

        # 空状态提示
        self.empty_label = tk.Label(self.grid_frame, text="点击「立即更新」开始采集图片",
                                    font=("Microsoft YaHei UI", 13), fg="#aaa", bg="#f0f0f0")
        self.empty_label.pack(expand=True)

        # ====== 底部状态栏 ======
        status_bar = tk.Frame(self.root, bg="#2d2d2d", height=32)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.stats_text = tk.StringVar(value="就绪")
        stats_label = tk.Label(status_bar, textvariable=self.stats_text, fg="#aaa", bg="#2d2d2d",
                               font=("Microsoft YaHei UI", 8), padx=15)
        stats_label.pack(side=tk.LEFT, pady=6)

        next_update_text = f"下次更新: 计算中..."
        self.next_update_label = tk.Label(status_bar, text=next_update_text, fg="#aaa", bg="#2d2d2d",
                                          font=("Microsoft YaHei UI", 8), padx=15)
        self.next_update_label.pack(side=tk.RIGHT, pady=6)

    def _on_canvas_configure(self, event):
        self.main_canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_filter_highlight(self):
        for site, btn in self.filter_buttons.items():
            if site == self.current_filter:
                btn.configure(fg="#fff", bg="#2d7fd9")
            else:
                btn.configure(fg="#666", bg="#f5f5f5")

    def _filter_by_site(self, site):
        self.current_filter = site
        self._update_filter_highlight()
        self._refresh_grid()

    def _load_existing_images(self):
        """加载已存在的图片到界面"""
        save_dir = self.config.get("save_dir", "")
        if not os.path.exists(save_dir):
            return

        for root_path, dirs, files in os.walk(save_dir):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    src = os.path.relpath(root_path, save_dir).replace('\\', '/')
                    if "cnu" in src.lower():
                        site = "CNU视觉联盟"
                    elif "500px" in src.lower():
                        site = "500px摄影社区"
                    elif "dili" in src.lower():
                        site = "中国国家地理"
                    else:
                        site = "未知"

                    filepath = os.path.join(root_path, f)

                    # 从 history 中查找匹配记录
                    matched = None
                    for item in self.history:
                        if item.get("filepath") == filepath:
                            matched = item
                            break

                    if not matched:
                        matched = {
                            "id": f"local_{hash(f)}",
                            "title": os.path.splitext(f)[0],
                            "site": site,
                            "author": "",
                            "filepath": filepath,
                            "url": "",
                            "page_url": "",
                            "date": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d"),
                            "category": "",
                        }
                        self.history.append(matched)

            save_history(self.history)

    def _refresh_grid(self):
        """重建缩略图网格"""
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        filtered = self.history
        if self.current_filter != "全部":
            filtered = [item for item in self.history
                        if item.get("site", "") == self.current_filter]

        if not filtered:
            self.empty_label = tk.Label(self.grid_frame, text="暂无图片",
                                        font=("Microsoft YaHei UI", 13), fg="#aaa", bg="#f0f0f0")
            self.empty_label.pack(expand=True, pady=60)
            self._update_stats()
            return

        thumb_size = self.config.get("thumbnail_size", 200)
        cols = max(1, (self.grid_frame.winfo_width() or 800) // (thumb_size + 30))

        row = 0
        col = 0
        for idx, item in enumerate(filtered):
            card = tk.Frame(self.grid_frame, bg="white", padx=3, pady=3,
                            highlightthickness=1, highlightbackground="#e0e0e0",
                            cursor="hand2")
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # 缩略图
            fp = item.get("filepath", "")
            thumb = make_thumbnail(fp, thumb_size)
            img_label = tk.Label(card, image=thumb, bg="#eee", cursor="hand2")
            img_label.image = thumb  # 保持引用
            img_label.pack()

            # 底部信息
            info_frame = tk.Frame(card, bg="white")
            info_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

            title = item.get("title", "无标题")[:20]
            tk.Label(info_frame, text=title, font=("Microsoft YaHei UI", 8, "bold"),
                     fg="#333", bg="white", anchor="w").pack(fill=tk.X)

            site_badge_color = {"CNU视觉联盟": "#e74c3c", "500px摄影社区": "#f39c12", "中国国家地理": "#27ae60"}
            site = item.get("site", "")
            badge_color = site_badge_color.get(site, "#888")

            bottom = tk.Frame(info_frame, bg="white")
            bottom.pack(fill=tk.X, pady=(2, 0))
            tk.Label(bottom, text=site, font=("Microsoft YaHei UI", 7),
                     fg=badge_color, bg="white").pack(side=tk.LEFT)
            tk.Label(bottom, text=get_relative_time(item.get("date", "")),
                     font=("Microsoft YaHei UI", 7), fg="#aaa", bg="white").pack(side=tk.RIGHT)

            # 点击事件
            for w in [card, img_label, info_frame, bottom]:
                w.bind("<Button-1>", lambda e, item=item: self._open_preview(item))

            # 右键菜单
            card.bind("<Button-3>", lambda e, item=item: self._show_context_menu(e, item))

            col += 1
            if col >= cols:
                col = 0
                row += 1

        self._update_stats()

    def _update_stats(self):
        total = len(self.history)
        by_site = {"CNU视觉联盟": 0, "500px摄影社区": 0, "中国国家地理": 0}
        total_size = 0
        for item in self.history:
            site = item.get("site", "")
            if site in by_site:
                by_site[site] += 1
            total_size += get_file_size_mb(item.get("filepath", ""))

        last_update = format_time(self.config.get("last_update_time", ""))
        stats = f"共 {total} 张图片  |  CNU: {by_site['CNU视觉联盟']} | 500px: {by_site['500px摄影社区']} | 国家地理: {by_site['中国国家地理']}  |  存储: {total_size:.1f} MB  |  上次更新: {last_update}"
        self.stats_text.set(stats)
        self.root.title(f"📷 摄影采集 - {total} 张图片")

    def _open_preview(self, item):
        try:
            self.preview_window = ImagePreviewWindow(self.root, item)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开预览: {e}")

    def navigate_preview(self, direction, current_item):
        """预览窗口中导航"""
        filtered = self.history
        if self.current_filter != "全部":
            filtered = [item for item in self.history if item.get("site", "") == self.current_filter]

        try:
            idx = filtered.index(current_item)
        except ValueError:
            return

        new_idx = idx + direction
        if 0 <= new_idx < len(filtered):
            new_item = filtered[new_idx]
            self.preview_window = ImagePreviewWindow(self.root, new_item)

    def _show_context_menu(self, event, item):
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 9))
        menu.add_command(label="预览", command=lambda: self._open_preview(item))
        menu.add_command(label="打开文件位置",
                         command=lambda: os.startfile(os.path.dirname(item.get("filepath", ""))))
        menu.add_separator()
        menu.add_command(label="删除", command=lambda: self._delete_image(item))
        menu.post(event.x_root, event.y_root)

    def _delete_image(self, item):
        if messagebox.askyesno("确认", "确定要删除这张图片吗？"):
            fp = item.get("filepath", "")
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except:
                    pass
            if item in self.history:
                self.history.remove(item)
            save_history(self.history)
            self._refresh_grid()

    def _open_save_folder(self):
        d = self.config.get("save_dir", "")
        if d and os.path.exists(d):
            os.startfile(d)
        else:
            messagebox.showinfo("提示", "保存目录不存在")

    def _open_settings(self):
        def on_settings_save(new_config):
            self.config = new_config
            self._refresh_grid()
            # 重新安排定时任务
            if self._update_job:
                self.root.after_cancel(self._update_job)
            self._schedule_next_update()

            # 开机启动
            try:
                setup_autostart(self.config.get("auto_startup", False))
            except:
                pass

        SettingsWindow(self.root, self.config, on_settings_save)

    def _start_fetch(self):
        if self.is_running:
            messagebox.showinfo("提示", "正在运行中，请稍候...")
            return
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        self._set_running(True)
        self._log_status("正在采集图片...")

        cfg = self.config
        new_results = scrape_all(
            save_dir=cfg.get("save_dir", "./downloads"),
            cnu_pages=cfg.get("cnu_pages", 3),
            px500_pages=cfg.get("500px_pages", 3),
            enable_cnu=cfg.get("cnu_enabled", True),
            enable_500px=cfg.get("500px_enabled", True),
            enable_dili=cfg.get("dili_enabled", True),
        )

        # 合并到历史
        new_count = 0
        for r in new_results:
            exists = any(h.get("id") == r["id"] for h in self.history)
            if not exists:
                self.history.append(r)
                new_count += 1

        # 清理超出容量的旧图片
        check_storage_limit(cfg)

        # 更新配置
        cfg["last_update_time"] = datetime.now().isoformat()
        save_config(cfg)
        save_history(self.history)

        self._set_running(False)
        self._log_status(f"完成！本轮新增 {new_count} 张图片 (共抓取 {len(new_results)} 张)")

        # 刷新UI (必须在主线程)
        self.root.after(0, self._refresh_grid)
        self.root.after(0, self._schedule_next_update)

    def _set_running(self, running):
        self.is_running = running
        if running:
            self.root.after(0, lambda: self.fetch_btn.configure(
                text="⏳ 采集中...", state=tk.DISABLED))
        else:
            self.root.after(0, lambda: self.fetch_btn.configure(
                text="🔄 立即更新", state=tk.NORMAL))

    def _log_status(self, msg):
        self.root.after(0, lambda: self.status_label.configure(text=msg))

    def _schedule_next_update(self):
        if self._update_job:
            self.root.after_cancel(self._update_job)

        interval = self.config.get("update_interval_hours", 5) * 3600 * 1000  # 毫秒
        self._update_job = self.root.after(interval, self._auto_fetch)

        next_time = datetime.now() + timedelta(milliseconds=interval)
        self.next_update_label.configure(
            text=f"下次更新: {next_time.strftime('%H:%M')} (每 {self.config.get('update_interval_hours', 5)} 小时)")

    def _auto_fetch(self):
        if not self.is_running:
            self._log_status("⏰ 定时更新触发...")
            threading.Thread(target=self._do_fetch, daemon=True).start()

    def _on_close(self):
        """关闭窗口"""
        # 保存状态
        save_history(self.history)
        self.root.destroy()


# ============================================================
# 启动入口
# ============================================================
def main():
    # 尝试设置 DPI 感知
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    root = tk.Tk()
    app = PhotoScraperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
