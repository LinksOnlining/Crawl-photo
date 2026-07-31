# -*- coding: utf-8 -*-
"""
摄影采集 - 爬虫模块 v3 (终极修复版)
修复:
  CNU:   裸 URL → 403, cover280 → 28KB 缩略图
         ✅ 访问 work 详情页 → imgs_json → 每张图用 style/content → 100+KB 高清原图
  500px:  baseUrl → 403
         ✅ baseUrl + !p4 → 200 OK, 原尺寸大图
  dili360: 境外 CDN 防盗链 → 国内 Windows 正常
         带 Referer + 完整浏览器头
"""
import requests, re, os, json, time, hashlib
from datetime import datetime
from urllib.parse import urljoin
from html import unescape as html_unescape

LOG_LINES = []

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)
    print(line)

CH = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
HH = {**CH, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}

MIN_SIZE = 10 * 1024  # 10KB minimum

def fetch(url, save_dir, prefix, uid="", referer="", retries=2):
    """下载图片 → (path, bytes) or (None, 0)"""
    if not url:
        return None, 0
    url = html_unescape(url.replace("&amp;", "&"))
    hdrs = dict(CH)
    if referer:
        hdrs["Referer"] = referer

    for _ in range(retries):
        try:
            resp = requests.get(url, headers=hdrs, timeout=30, stream=True)
            if resp.status_code != 200:
                return None, 0
            data = resp.content
            if len(data) < MIN_SIZE:
                return None, 0
            # detect extension
            ext = ".jpg"
            if data[:3] == b"\xff\xd8\xff":       ext = ".jpg"
            elif data[:8] == b"\x89PNG\r\n\x1a\n": ext = ".png"
            elif data[:4] == b"RIFF":              ext = ".webp"
            elif data[:4] == b"GIF8":              ext = ".gif"

            fname = f"{prefix}_{hashlib.md5(data).hexdigest()[:10]}_{uid}{ext}"
            fpath = os.path.join(save_dir, fname)
            if os.path.exists(fpath):
                return fpath, os.path.getsize(fpath)
            with open(fpath, "wb") as f:
                f.write(data)
            return fpath, len(data)
        except Exception as e:
            log(f"    fetch err: {str(e)[:40]}")
    return None, 0


# ═══════════════════════════════════════════════════════════
#  CNU 视觉联盟 — 深度抓取 work 页面全部高清大图
# ═══════════════════════════════════════════════════════════
def scrape_cnu(pages=3, save_dir="downloads"):
    """
    CNU 精选列表 API → 获取 work ID 列表
    → 访问每个 work 详情页 → imgs_json → 全部大图
    """
    results = []
    d = os.path.join(save_dir, "CNU视觉联盟")
    os.makedirs(d, exist_ok=True)
    log("═══ CNU 视觉联盟 ═══")

    # Step 1: 收集所有 work IDs
    work_ids = []
    for p in range(1, pages + 1):
        try:
            r = requests.get(f"http://www.cnu.cc/selectedsFlow/{p}", headers=HH, timeout=15)
            if r.status_code != 200: continue
            data = r.json()
            if data.get("status") != "success": continue
            for day in data.get("data", []):
                for w in day.get("works", []):
                    wid = w.get("id", "")
                    if wid:
                        work_ids.append((wid, w.get("title", ""), w.get("author_display_name", ""),
                                         day.get("date", ""), w.get("category", "")))
        except Exception as e:
            log(f"  API p{p} err: {e}")
        time.sleep(0.3)

    log(f"  API 获取 {len(work_ids)} 个作品")

    # Step 2: 遍历每个 work 详情页，提取全部图片
    for wid, title, author, date, category in work_ids:
        try:
            work_url = f"http://www.cnu.cc/works/{wid}"
            r = requests.get(work_url, headers=HH, timeout=15)
            if r.status_code != 200:
                log(f"  ⚠ [{title[:20]}] work page HTTP {r.status_code}")
                continue
            r.encoding = "utf-8"
            html = r.text

            # 提取 imgs_json 中的图片列表
            m = re.search(r'<div\s+id="imgs_json"[^>]*>(.*?)</div>', html, re.DOTALL)
            if not m:
                # 回退: 只用封面图 (首页看到的)
                cover_m = re.search(r'<img[^>]+src="(http://imgoss\.cnuc\.cc/[^"]+)"', html, re.I)
                if cover_m:
                    cover_url = html_unescape(cover_m.group(1).replace("&amp;", "&"))
                    cover_url = cover_url.replace("style/flow280", "style/content")
                    fpath, sz = fetch(cover_url, d, "cnu", wid[:6], referer=work_url)
                    if fpath:
                        results.append(dict(id=f"cnu_{wid}", title=title, author=author,
                                           site="CNU视觉联盟", filepath=fpath, size=sz,
                                           page_url=work_url, date=date, category=category))
                continue

            json_text = m.group(1)
            # HTML 转义还原
            json_text = html_unescape(json_text.replace("&quot;", '"').replace("&amp;", "&"))
            try:
                images = json.loads(json_text)
            except:
                log(f"  ⚠ [{title[:20]}] JSON 解析失败")
                continue

            if not isinstance(images, list):
                continue

            log(f"  [{title[:20]}] work 页发现 {len(images)} 张图片")

            for idx, img_info in enumerate(images):
                img_name = img_info.get("img", "")
                if not img_name:
                    continue
                # 图片路径格式: "2607/29/59af584f26bd36ab9c610414e302bb1c.jpg"
                img_url = f"http://imgoss.cnu.cc/{img_name}?x-oss-process=style/content"
                uid = f"{wid}_{idx}"
                fpath, sz = fetch(img_url, d, "cnu", uid, referer=work_url)
                if fpath:
                    results.append(dict(
                        id=f"cnu_{wid}_{idx}",
                        title=f"{title} #{idx+1}",
                        author=author,
                        site="CNU视觉联盟",
                        filepath=fpath, size=sz,
                        page_url=work_url,
                        date=date,
                        category=category,
                    ))
                else:
                    log(f"    ✗ 图片{idx+1} 下载失败")

            time.sleep(0.25)
        except Exception as e:
            log(f"  ⚠ [{title[:20]}] 异常: {e}")

    log(f"  ── CNU 完成: {len(results)} 张 ──")
    return results


# ═══════════════════════════════════════════════════════════
#  500px 摄影社区 — JSON API + !p4 原图
# ═══════════════════════════════════════════════════════════
def scrape_500px(pages=3, save_dir="downloads"):
    results = []
    seen = set()
    d = os.path.join(save_dir, "500px摄影社区")
    os.makedirs(d, exist_ok=True)
    log("═══ 500px 摄影社区 ═══")

    apis = [
        ("飙升榜", "https://500px.com.cn/community/discover/rankingRise?resourceType=0,2&page={}&size=30&type=json"),
        ("热门榜", "https://500px.com.cn/community/discover/hotPhotos?page={}&size=30&type=json"),
    ]

    for label, tpl in apis:
        for p in range(1, pages + 1):
            try:
                resp = requests.get(tpl.format(p), headers=HH, timeout=15)
                if resp.status_code != 200:
                    log(f"  [{label}] p{p} HTTP {resp.status_code}")
                    continue
                photos = resp.json()
                if not isinstance(photos, list):
                    continue

                for ph in photos:
                    pid = ph.get("id", "")
                    if pid in seen:
                        continue
                    seen.add(pid)

                    base = ph.get("url", {}).get("baseUrl", "")
                    if not base:
                        continue

                    # ⚡ 关键修复: 必须加尺寸后缀 !p4
                    img_url = f"{base}!p4" if "!" not in base else base

                    author = ph.get("uploaderInfo", {}).get("nickName", "未知")
                    uid = pid[:12]
                    fpath, sz = fetch(img_url, d, "500px", uid)

                    # 如果 !p4 失败，试 !p3
                    if not fpath and "!p4" in img_url:
                        fpath, sz = fetch(img_url.replace("!p4", "!p3"), d, "500px", uid)

                    if fpath:
                        results.append(dict(
                            id=f"500px_{pid}",
                            title=ph.get("title", "无标题"),
                            author=author,
                            site="500px摄影社区",
                            filepath=fpath, size=sz,
                            page_url=f"https://500px.com.cn/community/photo/{pid}",
                            date=datetime.now().strftime("%Y-%m-%d"),
                            category=label,
                            rating=ph.get("rating", 0),
                        ))
                time.sleep(0.3)
            except Exception as e:
                log(f"  [{label}] err: {e}")

    log(f"  ── 500px 完成: {len(results)} 张 ──")
    return results


# ═══════════════════════════════════════════════════════════
#  中国国家地理网
# ═══════════════════════════════════════════════════════════
def scrape_dili360(save_dir="downloads"):
    results = []
    seen = set()
    d = os.path.join(save_dir, "中国国家地理")
    os.makedirs(d, exist_ok=True)
    log("═══ 中国国家地理 ═══")

    pages = [
        ("首页", "https://www.dili360.com/"),
        ("旅行", "https://www.dili360.com/travel/"),
        ("自然", "https://www.dili360.com/nature/"),
        ("文化", "https://www.dili360.com/culture/"),
        ("图片", "https://www.dili360.com/photo/"),
    ]

    BAD = re.compile(r'(logo|icon|avatar|banner.ad|qrcode|search.btn|btn_|arrow|dot_|weixin|wechat|favicon|erweima|bg_)', re.I)

    for label, page_url in pages:
        try:
            resp = requests.get(page_url, headers=HH, timeout=20)
            if resp.status_code != 200:
                log(f"  [{label}] HTTP {resp.status_code}")
                continue
            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text

            imgs = re.findall(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)["\']', html, re.I)
            log(f"  [{label}] {len(imgs)} img tags")

            for src in imgs:
                src = html_unescape(src.replace("&amp;", "&"))
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urljoin(page_url, src)
                elif not src.startswith("http"):
                    src = urljoin(page_url, src)
                if not src or src in seen:
                    continue
                seen.add(src)
                if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', src, re.I):
                    continue
                if BAD.search(src.lower()):
                    continue

                uid = hashlib.md5(src.encode()).hexdigest()[:8]
                fpath, sz = fetch(src, d, "dili", uid, referer=page_url)
                if fpath:
                    results.append(dict(
                        id=f"dili_{uid}", title=os.path.basename(fpath),
                        author="中国国家地理", site="中国国家地理",
                        filepath=fpath, size=sz, page_url=page_url,
                        date=datetime.now().strftime("%Y-%m-%d"),
                        category=label,
                    ))
            time.sleep(0.4)
        except Exception as e:
            log(f"  [{label}] err: {e}")

    log(f"  ── 国家地理完成: {len(results)} 张 ──")
    return results


def run_scrape_all(cfg):
    log("╔══════════ 开始采集 ══════════╗")
    all_r = []
    base = cfg.get("save_dir", os.path.join(os.path.expanduser("~"), "Pictures", "PhotoScraper"))
    if cfg.get("cnu_enabled", True):
        try: all_r += scrape_cnu(cfg.get("cnu_pages", 3), base)
        except Exception as e: log(f"CNU 致命错: {e}")
    if cfg.get("500px_enabled", True):
        try: all_r += scrape_500px(cfg.get("500px_pages", 3), base)
        except Exception as e: log(f"500px 致命错: {e}")
    if cfg.get("dili_enabled", True):
        try: all_r += scrape_dili360(base)
        except Exception as e: log(f"dili360 致命错: {e}")
    log(f"╚════ 总计: {len(all_r)} 张 ════╝")
    return all_r


if __name__ == "__main__":
    cfg = {"save_dir": "./test_photos", "cnu_enabled": True, "cnu_pages": 1,
           "500px_enabled": True, "500px_pages": 1, "dili_enabled": True}
    r = run_scrape_all(cfg)
    for x in r:
        print(f"  ✅ [{x['site']}] {x['title'][:35]} — {x['size']/1024:.0f}KB")
