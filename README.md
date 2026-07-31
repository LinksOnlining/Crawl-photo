# 📷 摄影采集 - 图片采集桌面工具

一键采集中国国家地理网、CNU视觉联盟、500px摄影社区的高质量摄影作品。

---

## 🚀 快速开始

### 方案一：直接使用 EXE（推荐）

1. 双击运行 `build_exe.bat`
2. 等待打包完成（约 2-5 分钟）
3. 打开 `dist` 文件夹，双击 `摄影采集.exe` 即可使用

### 方案二：直接运行 Python 源码

```bash
# 1. 安装依赖
pip install -r requirements.txt --break-system-packages

# 2. 运行
python main.py
```

---

## ✨ 功能说明

- **多源采集**: 同时从三个摄影网站抓取图片
  - 中国国家地理网 (dili360.com) — 风光地理
  - CNU视觉联盟 (cnu.cc) — 视觉艺术/摄影作品
  - 500px摄影社区 (500px.com.cn) — 热门摄影排行
- **定时更新**: 每 5 小时自动抓取新图片（可在设置中调整）
- **缩略图浏览**: 网格视图浏览已采集的图片
- **大图预览**: 点击缩略图全屏查看
- **按来源筛选**: 分别查看不同网站的图片
- **存储管理**: 超出容量自动清理旧图片
- **开机自启**: 支持开机自动运行
- **系统托盘**: 最小化到系统托盘后台运行

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主程序（GUI界面） |
| `scrapers.py` | 爬虫模块（三个网站的采集逻辑） |
| `requirements.txt` | Python 依赖 |
| `build_exe.bat` | 一键打包脚本 |

---

## ⚙ 配置说明

首次运行会在程序目录生成 `config.json`：

```json
{
  "save_dir": "C:\\Users\\用户名\\Pictures\\摄影采集",
  "update_interval_hours": 5,
  "max_storage_gb": 5,
  "thumbnail_size": 200,
  "cnu_pages": 3,
  "500px_pages": 3,
  "cnu_enabled": true,
  "500px_enabled": true,
  "dili_enabled": true,
  "auto_startup": false
}
```

也可以在设置面板中直接修改。

---

## ⚠ 注意事项

1. 确保网络连接正常
2. 采集的图片仅供个人欣赏使用，请勿用于商业用途
3. 图片版权归原作者所有
4. 过高的采集频率可能导致 IP 被封，建议保持默认设置
5. 首次打包时 PyInstaller 需要联网下载依赖

---

## 🛠 系统要求

- Windows 10/11
- Python 3.8+ (仅打包时需要)
