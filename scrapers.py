"""
摄影网站图片采集工具 - 爬虫模块
支持: 中国国家地理网、CNU视觉联盟、500px摄影社区
"""

import requests
import re
import os
import hashlib
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 过滤规则：忽略这些小图/图标
MIN_IMAGE_SIZE_KB = 20  # 最小图片大小(KB)
IGNORE_PATTERNS = [
    r'(logo|icon|avatar|banner-ad|qrcode|favicon|btn_|button|arrow|dot_|bg_)',
    r'/\d+x\d+$',  # 太小的尺寸
    r'head\d+\.jpg',  # 头像
]

def is_valid_image_url(url):
    """判断是否为有效的图片URL"""
    if not url:
        return False
    url_lower = url.lower()
    if not any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return False
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, url_lower):
            return False
    return True

def normalize_url(url, base_url=""):
    """补全相对URL"""
    if not url:
        return url
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http'):
        return url
    if base_url:
        return urljoin(base_url, url)
    return url

def download_image(url, save_dir, site_name, image_id=""):
    """下载图片到指定目录，返回保存路径"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            return None

        content = resp.content
        if len(content) < MIN_IMAGE_SIZE_KB * 1024:
            return None

        # 用 URL 哈希命名
        ext = os.path.splitext(urlparse(url).path)[1] or '.jpg'
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            ext = '.jpg'
        filename = f"{site_name}_{hashlib.md5(url.encode()).hexdigest()[:12]}{ext}"

        filepath = os.path.join(save_dir, filename)
        if os.path.exists(filepath):
            return filepath

        with open(filepath, 'wb') as f:
            f.write(content)
        return filepath
    except Exception as e:
        print(f"[下载失败] {url}: {e}")
        return None


class ScraperCNU:
    """CNU视觉联盟爬虫"""
    name = "CNU视觉联盟"
    base_url = "http://www.cnu.cc"
    api_url = "http://www.cnu.cc/selectedsFlow/{}"
    img_base = "http://imgoss.cnu.cc/"

    @staticmethod
    def scrape(pages=5, save_dir="downloads"):
        results = []
        site_dir = os.path.join(save_dir, "cnu")
        os.makedirs(site_dir, exist_ok=True)

        for page in range(1, pages + 1):
            try:
                url = ScraperCNU.api_url.format(page)
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if data.get("status") != "success":
                    continue

                for day_data in data.get("data", []):
                    for work in day_data.get("works", []):
                        cover = work.get("cover", "")
                        if not cover:
                            continue

                        # 去掉阿里云OSS处理参数获得大图
                        img_url = ScraperCNU.img_base + cover
                        img_url = re.sub(r'&x-oss-process=[^&]+', '', img_url)
                        if '?' not in img_url:
                            img_url = img_url.split('?')[0]

                        photo_id = f"cnu_{work.get('id', '')}"
                        filepath = download_image(img_url, site_dir, "cnu", photo_id)
                        if filepath:
                            results.append({
                                "id": photo_id,
                                "title": work.get("title", "无标题"),
                                "author": work.get("author_display_name", "未知"),
                                "site": ScraperCNU.name,
                                "url": img_url,
                                "filepath": filepath,
                                "page_url": f"http://www.cnu.cc/works/{work.get('id', '')}",
                                "date": day_data.get("date", ""),
                                "category": work.get("category", ""),
                            })
                time.sleep(0.5)
            except Exception as e:
                print(f"[CNU] 第{page}页抓取失败: {e}")
                continue

        return results


class Scraper500px:
    """500px摄影社区爬虫"""
    name = "500px摄影社区"
    api_urls = [
        "https://500px.com.cn/community/discover/rankingRise?resourceType=0,2&page={}&size=30&type=json",
        "https://500px.com.cn/community/discover/hotPhotos?page={}&size=30&type=json",
    ]

    @staticmethod
    def scrape(pages=3, save_dir="downloads"):
        results = []
        seen_ids = set()
        site_dir = os.path.join(save_dir, "500px")
        os.makedirs(site_dir, exist_ok=True)

        for api_template in Scraper500px.api_urls:
            for page in range(1, pages + 1):
                try:
                    url = api_template.format(page)
                    resp = requests.get(url, headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue
                    photos = resp.json()
                    if not isinstance(photos, list):
                        continue

                    for photo in photos:
                        photo_id = photo.get("id", "")
                        if photo_id in seen_ids:
                            continue
                        seen_ids.add(photo_id)

                        img_url = ""
                        if "url" in photo:
                            img_url = photo["url"].get("baseUrl", "") or photo["url"].get("p3", "") or photo["url"].get("p4", "")

                        if not img_url:
                            continue

                        author = ""
                        if "uploaderInfo" in photo:
                            author = photo["uploaderInfo"].get("nickName", "未知")

                        fid = f"500px_{photo_id}"
                        filepath = download_image(img_url, site_dir, "500px", fid)
                        if filepath:
                            results.append({
                                "id": fid,
                                "title": photo.get("title", "无标题"),
                                "author": author,
                                "site": Scraper500px.name,
                                "url": img_url,
                                "filepath": filepath,
                                "page_url": f"https://500px.com.cn/community/photo/{photo_id}",
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "category": photo.get("categoryId", ""),
                                "rating": photo.get("rating", 0),
                            })
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[500px] 抓取失败: {e}")
                    continue

        return results


class ScraperDili360:
    """中国国家地理网爬虫"""
    name = "中国国家地理"
    base_url = "https://www.dili360.com"
    urls_to_scrape = [
        "https://www.dili360.com/",
        "https://www.dili360.com/travel/",
        "https://www.dili360.com/nature/",
    ]

    @staticmethod
    def scrape(save_dir="downloads"):
        results = []
        seen_urls = set()
        site_dir = os.path.join(save_dir, "dili360")
        os.makedirs(site_dir, exist_ok=True)

        for page_url in ScraperDili360.urls_to_scrape:
            try:
                resp = requests.get(page_url, headers=HEADERS, timeout=20)
                if resp.status_code != 200:
                    continue

                # 处理编码
                resp.encoding = resp.apparent_encoding or 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')

                img_tags = soup.find_all('img')
                for img in img_tags:
                    src = img.get('src') or img.get('data-src') or img.get('data-original') or ''
                    if not src:
                        continue

                    src = normalize_url(src, page_url)
                    if not is_valid_image_url(src):
                        continue
                    if src in seen_urls:
                        continue
                    seen_urls.add(src)

                    # 获取上下文信息
                    parent_a = img.find_parent('a')
                    link_url = ""
                    if parent_a and parent_a.get('href'):
                        link_url = normalize_url(parent_a['href'], page_url)

                    alt_text = img.get('alt', '') or img.get('title', '')
                    if not alt_text:
                        # 尝试从父元素获取标题
                        parent = img.find_parent(['div', 'li', 'figure'])
                        if parent:
                            heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                            if heading:
                                alt_text = heading.get_text(strip=True)

                    fid = f"dili_{hashlib.md5(src.encode()).hexdigest()[:12]}"
                    filepath = download_image(src, site_dir, "dili360", fid)
                    if filepath:
                        results.append({
                            "id": fid,
                            "title": alt_text or os.path.basename(filepath),
                            "author": "中国国家地理",
                            "site": ScraperDili360.name,
                            "url": src,
                            "filepath": filepath,
                            "page_url": link_url or page_url,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "category": "风光地理",
                        })
                time.sleep(0.5)
            except Exception as e:
                print(f"[dili360] 抓取失败 {page_url}: {e}")
                continue

        return results


def scrape_all(save_dir="downloads", cnu_pages=5, px500_pages=3, enable_cnu=True, enable_500px=True, enable_dili=True):
    """统一爬取入口"""
    all_results = []

    if enable_cnu:
        print(f"[开始] 抓取CNU视觉联盟...")
        try:
            r = ScraperCNU.scrape(pages=cnu_pages, save_dir=save_dir)
            all_results.extend(r)
            print(f"[完成] CNU: {len(r)} 张")
        except Exception as e:
            print(f"[错误] CNU: {e}")

    if enable_500px:
        print(f"[开始] 抓取500px...")
        try:
            r = Scraper500px.scrape(pages=px500_pages, save_dir=save_dir)
            all_results.extend(r)
            print(f"[完成] 500px: {len(r)} 张")
        except Exception as e:
            print(f"[错误] 500px: {e}")

    if enable_dili:
        print(f"[开始] 抓取中国国家地理...")
        try:
            r = ScraperDili360.scrape(save_dir=save_dir)
            all_results.extend(r)
            print(f"[完成] 国家地理: {len(r)} 张")
        except Exception as e:
            print(f"[错误] 国家地理: {e}")

    print(f"[总计] 本轮抓取: {len(all_results)} 张新图片")
    return all_results


if __name__ == "__main__":
    results = scrape_all(save_dir="./test_downloads")
    for r in results:
        print(f"  [{r['site']}] {r['title'][:30]} - {r['filepath']}")
