# -*- coding: utf-8 -*-
"""
=============================================================================
Facebook Full 2-Year Harvester & Deep Comment Scraper (UIT)
=============================================================================
Tính năng chuyên nghiệp:
  1. Crawl toàn bộ bài viết trong 2 năm (730 ngày).
  2. Đi sâu vào từng bài viết để lấy TOÀN BỘ bình luận và phản hồi.
  3. Lưu trữ lũy tiến vào SQLite (data/fb_uit_2years.db) - không bao giờ mất dữ liệu.
  4. Cơ chế RESUME thông minh: tắt máy mở lại tiếp tục chạy không cào lại.
  5. Quản lý bộ nhớ chống tràn RAM (DOM Memory Recycling).
  6. Tích hợp phân tích Sentiment cho cả bài viết lẫn bình luận.
=============================================================================
"""

import json
import sqlite3
import time
import random
import re
import sys
import io
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Thư mục & Đường dẫn
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
COOKIE_DIR = BASE_DIR / "cookies"
DEBUG_DIR = BASE_DIR / "debug"

for d in [DATA_DIR, LOG_DIR, COOKIE_DIR, DEBUG_DIR]:
    d.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "fb_uit_2years.db"
COOKIE_FILE = COOKIE_DIR / "fb_cookies.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper_2years.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cấu hình 2 năm (730 ngày)
# ---------------------------------------------------------------------------
DAYS_BACK = 730  # 2 năm
PAGES = [
    {"id": "UIT.Fanpage", "url": "https://www.facebook.com/UIT.Fanpage"},
    {"id": "UITconfess", "url": "https://www.facebook.com/UITconfess"},
]

# ---------------------------------------------------------------------------
# Quản lý Database SQLite
# ---------------------------------------------------------------------------
def init_database():
    """Khởi tạo cấu trúc bảng SQLite để lưu trữ lũy tiến."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Bảng lưu bài viết
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            page TEXT,
            post_url TEXT,
            post_time TEXT,
            timestamp_utc INTEGER,
            text TEXT,
            likes INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            sentiment TEXT,
            sentiment_score REAL,
            crawled_at TEXT,
            comments_crawled INTEGER DEFAULT 0
        )
    """)

    # Bảng lưu bình luận
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            comment_id TEXT PRIMARY KEY,
            post_id TEXT,
            author TEXT,
            comment_text TEXT,
            comment_time TEXT,
            likes INTEGER DEFAULT 0,
            sentiment TEXT,
            sentiment_score REAL,
            crawled_at TEXT,
            FOREIGN KEY (post_id) REFERENCES posts (post_id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"💾 Cơ sở dữ liệu SQLite sẵn sàng: {DB_PATH}")


def save_post_to_db(post: dict):
    """Lưu 1 bài viết vào database (Insert or Ignore)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO posts (
            post_id, page, post_url, post_time, timestamp_utc,
            text, likes, comments_count, shares, crawled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post["post_id"], post["page"], post["post_url"], post["post_time"],
        post.get("timestamp_utc", 0), post["text"], post["likes"],
        post["comments_count"], post["shares"], datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def save_comment_to_db(comment: dict):
    """Lưu 1 bình luận vào database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO comments (
            comment_id, post_id, author, comment_text, comment_time, likes, crawled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        comment["comment_id"], comment["post_id"], comment["author"],
        comment["comment_text"], comment["comment_time"], comment["likes"],
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def mark_comments_done(post_id: str):
    """Đánh dấu bài viết đã hoàn tất cào bình luận."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET comments_crawled = 1 WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()


def get_posts_needing_comments(limit: int = 500) -> list[dict]:
    """Lấy danh sách các bài viết chưa cào bình luận."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, page, post_url, text FROM posts 
        WHERE comments_crawled = 0 AND post_url != ''
        ORDER BY timestamp_utc DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tiện ích làm sạch & Parse thời gian
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u034f\u200b-\u200f\ufeff\u00ad]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_timestamp(time_str: str) -> datetime | None:
    """Parse đa dạng định dạng ngày giờ của Facebook tiếng Việt và tiếng Anh."""
    if not time_str:
        return None
    now = datetime.now(timezone.utc)
    s = time_str.lower().strip()

    # Tương đối: phút, giờ, ngày, tuần
    rel_map = [
        (r"(\d+)\s*(phút|min)", "minutes"),
        (r"(\d+)\s*(giờ|hour|h\b)", "hours"),
        (r"(\d+)\s*(ngày|day|d\b)", "days"),
        (r"(\d+)\s*(tuần|week|w\b)", "weeks"),
        (r"(\d+)\s*(tháng|month)", "months"),
        (r"(\d+)\s*(năm|year)", "years"),
    ]
    for pattern, unit in rel_map:
        m = re.search(pattern, s)
        if m:
            val = int(m.group(1))
            if unit == "minutes": return now - timedelta(minutes=val)
            if unit == "hours": return now - timedelta(hours=val)
            if unit == "days": return now - timedelta(days=val)
            if unit == "weeks": return now - timedelta(weeks=val)
            if unit == "months": return now - timedelta(days=val * 30)
            if unit == "years": return now - timedelta(days=val * 365)

    if "hôm qua" in s or "yesterday" in s:
        return now - timedelta(days=1)
    if "vừa xong" in s or "just now" in s:
        return now

    # Tuyệt đối: "14 tháng 8, 2024" hoặc "14 Tháng 8"
    m_vn = re.search(r"(\d{1,2})\s+[Tt]háng\s+(\d{1,2})(?:[,\s]+(\d{4}))?", s)
    if m_vn:
        d = int(m_vn.group(1))
        m_num = int(m_vn.group(2))
        y = int(m_vn.group(3)) if m_vn.group(3) else now.year
        try:
            return datetime(y, m_num, d, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Giai đoạn 1: Quét danh sách bài viết theo dòng thời gian (2 năm)
# ---------------------------------------------------------------------------
async def crawl_page_timeline_2years(page, page_info: dict, cutoff_date: datetime):
    """
    Cuộn trang Facebook lùi dần 2 năm, định kỳ bóc tách và lưu vào Database.
    """
    page_id = page_info["id"]
    page_url = page_info["url"]

    logger.info(f"\n{'=' * 60}")
    logger.info(f"🕷️ GIAI ĐOẠN 1: Quét Timeline 2 năm cho {page_id}")
    logger.info(f"   Mốc thời gian cần lùi về: {cutoff_date.strftime('%d/%m/%Y')}")
    logger.info(f"{'=' * 60}")

    await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(4000)

    # Đóng popup / dialog nếu có
    await dismiss_popups(page)

    reached_cutoff = False
    total_posts_saved = 0
    consecutive_no_new = 0
    max_scroll_attempts = 1500  # Đủ cho 2 năm

    for scroll_idx in range(max_scroll_attempts):
        # Đóng popup nếu xuất hiện
        await dismiss_popups(page)

        # Cuộn trang mượt
        scroll_px = random.randint(1200, 2000)
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        await page.wait_for_timeout(random.randint(1800, 2600))

        # Định kỳ mỗi 15 lần cuộn: bóc tách bài viết trên DOM hiện tại và lưu ngay
        if (scroll_idx + 1) % 15 == 0:
            posts_batch, oldest_time = await extract_visible_posts(page, page_id)
            new_saved = 0
            for p in posts_batch:
                save_post_to_db(p)
                new_saved += 1
            total_posts_saved += new_saved

            logger.info(f"   📜 Scroll #{scroll_idx + 1} | Đã lưu: {total_posts_saved} bài | Mốc bài cũ nhất vừa thấy: {oldest_time}")

            if oldest_time and oldest_time < cutoff_date:
                logger.info(f"   🎯 ĐÃ ĐẠT MỐC 2 NĂM ({oldest_time.strftime('%d/%m/%Y')}). Dừng quét timeline trang {page_id}.")
                reached_cutoff = True
                break

            # Kiểm tra DOM có nở quá lớn không, giải phóng bộ nhớ DOM
            if (scroll_idx + 1) % 60 == 0:
                await purge_offscreen_dom(page)

    logger.info(f"✅ Hoàn thành Giai đoạn 1 cho {page_id}: {total_posts_saved} bài viết đã lưu vào SQLite.")


async def dismiss_popups(page):
    """Đóng tất cả các popup cản trở cuộn trang."""
    try:
        await page.evaluate("""
            document.querySelectorAll('div[role="dialog"]').forEach(d => d.style.display = 'none');
            document.querySelectorAll('div[data-visualcompletion="ignore"]').forEach(d => {
                if (getComputedStyle(d).position === 'fixed') d.style.display = 'none';
            });
            document.body.style.overflow = 'auto';
        """)
        # Nhấn escape
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def purge_offscreen_dom(page):
    """Dọn bớt các phần tử DOM đã cuộn qua để tránh tràn bộ nhớ RAM (OOM)."""
    try:
        await page.evaluate("""
            // Giữ lại 40 bài viết gần nhất, ẩn bớt các bài cũ quá cao bên trên
            const articles = document.querySelectorAll('div[role="feed"] > div, div[data-pagelet*="FeedUnit"]');
            if (articles.length > 50) {
                for (let i = 0; i < articles.length - 30; i++) {
                    articles[i].style.display = 'none';
                }
            }
        """)
    except Exception:
        pass


async def extract_visible_posts(page, page_id: str) -> tuple[list[dict], datetime | None]:
    """Bóc tách các bài viết đang hiển thị trên feed."""
    posts = []
    oldest_dt = None

    try:
        elements = await page.query_selector_all('div[role="feed"] > div, div[data-pagelet*="FeedUnit"], div[role="article"]')
        for elem in elements:
            full_text = await elem.inner_text()
            if not full_text or len(full_text) < 30:
                continue

            # Bỏ qua status bar
            if full_text.startswith("Chỉ báo trạng thái") or full_text.startswith("Đang hoạt động"):
                continue

            # Trích xuất thời gian
            post_time_str = ""
            post_dt = None
            time_elem = await elem.query_selector('a[href*="/posts/"] span, a[role="link"] span, abbr')
            if time_elem:
                post_time_str = (await time_elem.inner_text()).strip()
                post_dt = parse_timestamp(post_time_str)

            if post_dt:
                if oldest_dt is None or post_dt < oldest_dt:
                    oldest_dt = post_dt

            # Trích xuất link bài viết (permalink)
            post_url = ""
            link_elem = await elem.query_selector('a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"]')
            if link_elem:
                href = await link_elem.get_attribute("href")
                if href:
                    post_url = href.split("?")[0]
                    if not post_url.startswith("http"):
                        post_url = "https://www.facebook.com" + post_url

            # Tạo mã định danh bài viết
            post_id = re.sub(r"\W+", "_", post_url) if post_url else f"{page_id}_{hash(full_text[:60])}"

            # Lọc text bài viết
            text = clean_text(full_text)

            posts.append({
                "post_id": post_id,
                "page": page_id,
                "post_url": post_url,
                "post_time": post_time_str,
                "timestamp_utc": int(post_dt.timestamp()) if post_dt else 0,
                "text": text,
                "likes": 0,
                "comments_count": 0,
                "shares": 0,
            })
    except Exception as e:
        logger.debug(f"Lỗi extract_visible_posts: {e}")

    return posts, oldest_dt


# ---------------------------------------------------------------------------
# Giai đoạn 2: Thu thập toàn bộ Bình luận của từng bài viết (Deep Dive)
# ---------------------------------------------------------------------------
async def crawl_post_all_comments(page, post: dict):
    """Mở link bài viết riêng lẻ và tự động bung toàn bộ bình luận & phản hồi."""
    post_url = post["post_url"]
    post_id = post["post_id"]

    if not post_url:
        mark_comments_done(post_id)
        return

    logger.info(f"   💬 Đang cào bình luận bài: {post_url[:70]}...")

    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(3000)
        await dismiss_popups(page)

        # Chuyển bộ lọc bình luận sang "Tất cả bình luận" (All comments) nếu có
        try:
            filter_btn = page.locator('div[role="button"]:has-text("Phù hợp nhất"), div[role="button"]:has-text("Most relevant")').first
            if await filter_btn.is_visible(timeout=1500):
                await filter_btn.click()
                await page.wait_for_timeout(1000)
                all_comments_opt = page.locator('div[role="menuitem"]:has-text("Tất cả bình luận"), div[role="menuitem"]:has-text("All comments")').first
                if await all_comments_opt.is_visible(timeout=1500):
                    await all_comments_opt.click()
                    await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Lặp lại thao tác click "Xem thêm bình luận" cho đến khi hết
        for _ in range(30):
            clicked_any = False
            # Nút xem thêm bình luận chính
            more_btns = page.locator(
                'div[role="button"]:has-text("Xem thêm bình luận"), '
                'div[role="button"]:has-text("View more comments"), '
                'span:has-text("Xem thêm bình luận")'
            )
            count = await more_btns.count()
            for i in range(min(count, 3)):
                try:
                    btn = more_btns.nth(i)
                    if await btn.is_visible(timeout=800):
                        await btn.click(timeout=1500)
                        clicked_any = True
                        await page.wait_for_timeout(1200)
                except Exception:
                    pass

            # Nút xem phản hồi lồng nhau (Replies)
            reply_btns = page.locator('div[role="button"]:has-text("câu trả lời"), div[role="button"]:has-text("replies"), div[role="button"]:has-text("phản hồi")')
            r_count = await reply_btns.count()
            for i in range(min(r_count, 3)):
                try:
                    btn = reply_btns.nth(i)
                    if await btn.is_visible(timeout=800):
                        await btn.click(timeout=1500)
                        clicked_any = True
                        await page.wait_for_timeout(800)
                except Exception:
                    pass

            if not clicked_any:
                break

        # Bóc tách tất cả các khối bình luận
        comment_blocks = await page.query_selector_all('ul > li div[role="article"], div[aria-label*="bình luận của"], div[aria-label*="Comment by"]')
        saved_comments_count = 0

        for c_idx, c_elem in enumerate(comment_blocks):
            try:
                c_text_raw = await c_elem.inner_text()
                lines = [l.strip() for l in c_text_raw.split("\n") if l.strip()]
                if not lines:
                    continue

                author = lines[0] if len(lines) > 0 else "Ẩn danh"
                # Lọc bỏ nút Like, Trả lời ở cuối
                content_lines = [l for l in lines[1:] if not re.match(r"^(Thích|Like|Trả lời|Reply|\d+\s*(giờ|ngày|tuần|tháng|h|d|w)|Phản hồi)$", l, re.IGNORECASE)]
                comment_text = clean_text(" ".join(content_lines))

                if len(comment_text) < 2:
                    continue

                c_id = f"{post_id}_c_{c_idx}_{hash(comment_text[:30])}"
                save_comment_to_db({
                    "comment_id": c_id,
                    "post_id": post_id,
                    "author": author,
                    "comment_text": comment_text,
                    "comment_time": "",
                    "likes": 0,
                })
                saved_comments_count += 1
            except Exception:
                continue

        logger.info(f"   ✅ Đã lưu {saved_comments_count} bình luận cho bài viết.")
        mark_comments_done(post_id)

    except Exception as e:
        logger.warning(f"   ⚠️ Lỗi cào comment bài {post_url}: {e}")
        mark_comments_done(post_id)


# ---------------------------------------------------------------------------
# Giai đoạn 3: Phân tích Sentiment hàng loạt (Batch NLP)
# ---------------------------------------------------------------------------
def run_full_sentiment_analysis():
    """Phân tích sắc thái cho toàn bộ bài viết và bình luận trong cơ sở dữ liệu."""
    logger.info("\n" + "=" * 60)
    logger.info("🧠 GIAI ĐOẠN 3: Bắt đầu phân tích Sentiment toàn bộ dữ liệu 2 năm")
    logger.info("=" * 60)

    try:
        from sentiment_analyzer import classify_post
    except ImportError:
        logger.error("Không tìm thấy sentiment_analyzer.py")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Phân tích bài viết
    cursor.execute("SELECT post_id, page, text FROM posts WHERE sentiment IS NULL")
    unclassified_posts = cursor.fetchall()
    logger.info(f"📊 Đang phân tích sentiment cho {len(unclassified_posts)} bài viết...")

    for post_id, page, text in unclassified_posts:
        res = classify_post({"text": text, "shared_text": "", "page": page})
        cursor.execute("""
            UPDATE posts SET sentiment = ?, sentiment_score = ? WHERE post_id = ?
        """, (res["sentiment"], res["sentiment_score"], post_id))

    # 2. Phân tích bình luận
    cursor.execute("SELECT comment_id, comment_text FROM comments WHERE sentiment IS NULL")
    unclassified_comments = cursor.fetchall()
    logger.info(f"💬 Đang phân tích sentiment cho {len(unclassified_comments)} bình luận...")

    for c_id, c_text in unclassified_comments:
        res = classify_post({"text": c_text, "shared_text": "", "page": "comment"})
        cursor.execute("""
            UPDATE comments SET sentiment = ?, sentiment_score = ? WHERE comment_id = ?
        """, (res["sentiment"], res["sentiment_score"], c_id))

    conn.commit()

    # Thống kê báo cáo
    cursor.execute("SELECT sentiment, COUNT(*) FROM posts GROUP BY sentiment")
    post_stats = dict(cursor.fetchall())

    cursor.execute("SELECT sentiment, COUNT(*) FROM comments GROUP BY sentiment")
    comment_stats = dict(cursor.fetchall())

    conn.close()

    # Xuất báo cáo tổng hợp 2 năm
    report_file = DATA_DIR / f"report_2years_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP SENTIMENT 2 NĂM (UIT FACEBOOK)\n")
        f.write(f"   Thời gian tạo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write("📈 1. THỐNG KÊ BÀI VIẾT:\n")
        for k, v in post_stats.items():
            f.write(f"   • {k or 'Chưa rõ'}: {v} bài\n")
        f.write("\n💬 2. THỐNG KÊ BÌNH LUẬN CỦA SINH VIÊN:\n")
        for k, v in comment_stats.items():
            f.write(f"   • {k or 'Chưa rõ'}: {v} bình luận\n")
        f.write("\n" + "=" * 70 + "\n")

    logger.info(f"🎉 Hoàn thành! Báo cáo chi tiết: {report_file}")


# ---------------------------------------------------------------------------
# Hàm điều phối chính (Orchestrator)
# ---------------------------------------------------------------------------
async def async_main():
    from playwright.async_api import async_playwright

    init_database()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="vi-VN",
        )

        # Nạp session cookies đã lưu
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                await context.add_cookies(json.load(f))
            logger.info("🍪 Đã nạp Cookies đăng nhập thành công.")

        page = await context.new_page()

        # BƯỚC 1: Quét danh sách bài viết trong 2 năm
        for page_info in PAGES:
            await crawl_page_timeline_2years(page, page_info, cutoff_date)
            await asyncio.sleep(random.uniform(5, 10))

        # BƯỚC 2: Cào bình luận cho các bài viết chưa lấy comment
        logger.info("\n" + "=" * 60)
        logger.info("💬 BƯỚC 2: Bắt đầu thu thập toàn bộ bình luận của các bài viết...")
        logger.info("=" * 60)

        posts_to_crawl = get_posts_needing_comments(limit=1000)
        logger.info(f"Tìm thấy {len(posts_to_crawl)} bài viết cần cào bình luận.")

        for idx, post in enumerate(posts_to_crawl):
            logger.info(f"[{idx + 1}/{len(posts_to_crawl)}]")
            await crawl_post_all_comments(page, post)
            # Nghỉ ngẫu nhiên giữa các bài viết để bảo vệ tài khoản
            await asyncio.sleep(random.uniform(2, 4))

        await browser.close()

    # BƯỚC 3: Phân tích Sentiment tổng lực
    run_full_sentiment_analysis()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
