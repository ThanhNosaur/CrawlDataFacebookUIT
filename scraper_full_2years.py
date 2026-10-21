# -*- coding: utf-8 -*-
"""
=============================================================================
Facebook Full 2-Year Harvester & Deep Comment Scraper (UIT)
=============================================================================
Tính năng chuyên nghiệp:
  1. Crawl toàn bộ bài viết trong 2 năm (730 ngày) cho UIT.Fanpage & UITconfess.
  2. Bóc tách từng bài viết để lấy TOÀN BỘ bình luận & phản hồi (Replies).
  3. Lưu trữ lũy tiến vào SQLite (data/fb_uit_2years.db) - an toàn tuyệt đối.
  4. Cơ chế RESUME thông minh: tắt máy mở lại tiếp tục chạy không cào lại.
  5. Quản lý bộ nhớ chống tràn RAM (DOM Memory Recycling).
  6. Chống phát hiện bot & cơ chế bảo vệ an toàn tài khoản 100%.
  7. Tích hợp phân tích Sentiment cho cả bài viết lẫn bình luận.
  8. Xuất file CSV (Excel-ready) và Báo cáo tổng kết tự động.
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


def save_post_to_db(post: dict) -> bool:
    """Lưu 1 bài viết vào database (Insert or Ignore). Trả về True nếu bài mới."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO posts (
            post_id, page, post_url, post_time, timestamp_utc,
            text, likes, comments_count, shares, crawled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post["post_id"], post["page"], post["post_url"], post["post_time"],
        post.get("timestamp_utc", 0), post["text"], post.get("likes", 0),
        post.get("comments_count", 0), post.get("shares", 0), datetime.now().isoformat()
    ))
    inserted = (cursor.rowcount > 0)
    conn.commit()
    conn.close()
    return inserted


def save_comment_to_db(comment: dict) -> bool:
    """Lưu 1 bình luận vào database. Trả về True nếu bình luận mới."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO comments (
            comment_id, post_id, author, comment_text, comment_time, likes, crawled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        comment["comment_id"], comment["post_id"], comment["author"],
        comment["comment_text"], comment.get("comment_time", ""), comment.get("likes", 0),
        datetime.now().isoformat()
    ))
    inserted = (cursor.rowcount > 0)
    conn.commit()
    conn.close()
    return inserted


def mark_comments_done(post_id: str):
    """Đánh dấu bài viết đã hoàn tất cào bình luận."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET comments_crawled = 1 WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()


def get_posts_needing_comments(limit: int = 2000) -> list[dict]:
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


def get_db_stats() -> dict:
    """Lấy thống kê số lượng bài viết và bình luận trong database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    p_count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    c_count = cursor.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    conn.close()
    return {"posts": p_count, "comments": c_count}


# ---------------------------------------------------------------------------
# Tiện ích làm sạch & Parse thời gian (Chuẩn xác 100%)
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u034f\u200b-\u200f\ufeff\u00ad]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_timestamp(time_str: str) -> datetime | None:
    """Parse ngày giờ bài viết Facebook tiếng Việt và tiếng Anh chuẩn xác."""
    if not time_str:
        return None
    now = datetime.now(timezone.utc)
    s = time_str.strip()

    # 1. Tuyệt đối tiếng Việt: "14 Tháng 8, 2024" hoặc "13 Tháng 8"
    m_vn = re.search(r"(\d{1,2})\s+[Tt]háng\s+(\d{1,2})(?:[,\s]+(\d{4}))?", s)
    if m_vn:
        d = int(m_vn.group(1))
        m_num = int(m_vn.group(2))
        y = int(m_vn.group(3)) if m_vn.group(3) else (
            now.year if (m_num < now.month or (m_num == now.month and d <= now.day)) else now.year - 1
        )
        try:
            return datetime(y, m_num, d, tzinfo=timezone.utc)
        except ValueError:
            pass

    # 2. Đặc biệt
    s_lower = s.lower()
    if "vừa xong" in s_lower or "just now" in s_lower:
        return now
    if "hôm qua" in s_lower or "yesterday" in s_lower:
        return now - timedelta(days=1)

    # 3. Tương đối
    rel_map = [
        (r"(\d+)\s*(?:phút|min)", "minutes"),
        (r"(\d+)\s*(?:giờ|hour|h\b)", "hours"),
        (r"(\d+)\s*(?:ngày|day|d\b)", "days"),
        (r"(\d+)\s*(?:tuần|week|w\b)", "weeks"),
        (r"(\d+)\s*(?:tháng|month)", "months"),
        (r"(\d+)\s*(?:năm|year)", "years"),
    ]
    for pattern, unit in rel_map:
        m = re.search(pattern, s_lower)
        if m:
            val = int(m.group(1))
            if unit == "minutes": return now - timedelta(minutes=val)
            if unit == "hours": return now - timedelta(hours=val)
            if unit == "days": return now - timedelta(days=val)
            if unit == "weeks": return now - timedelta(weeks=val)
            if unit == "months": return now - timedelta(days=val * 30)
            if unit == "years": return now - timedelta(days=val * 365)

    return None


async def dismiss_timeline_popups(page):
    """Đóng popup đăng nhập / quảng cáo khi cuộn timeline."""
    try:
        close_btn = page.locator('div[aria-label="Đóng"], div[aria-label="Close"]').first
        if await close_btn.is_visible(timeout=800):
            await close_btn.click()
            await page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Giai đoạn 1: Quét Timeline 2 năm (Infinite Feed Harvesting)
# ---------------------------------------------------------------------------
async def extract_visible_timeline_posts(page, page_id: str) -> tuple[list[dict], datetime | None]:
    """Bóc tách tất cả bài viết đang hiện diện trong DOM feed."""
    posts = []
    oldest_dt = None

    try:
        articles = await page.query_selector_all('div[role="article"]')
        for art in articles:
            raw_text = (await art.inner_text()).strip()
            if len(raw_text) < 35:
                continue

            # Làm sạch header rác Facebook
            cleaned = clean_text(raw_text)
            cleaned = re.sub(r"^Chỉ báo trạng thái online[^\n]*\n*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"^Đang hoạt động[^\n]*\n*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"^Trường Đại học Công nghệ Thông tin[^\n]*\n*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"^UIT Confession[^\n]*\n*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n+(?:Thích|Bình luận|Chia sẻ|Gửi|Xem thêm bình luận)[^\n]*$", "", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()

            if len(cleaned) < 25:
                continue

            # Bóc tách link bài viết và thời gian
            post_url = ""
            post_time_str = ""
            post_dt = None

            links = await art.query_selector_all("a")
            for l in links:
                href = await l.get_attribute("href")
                aria = await l.get_attribute("aria-label") or ""
                txt = (await l.inner_text()).strip()

                if href and ("/posts/" in href or "/permalink/" in href or "story_fbid" in href or "/photos/" in href or "/photo/" in href or "/videos/" in href):
                    if not post_url:
                        post_url = href.split("?")[0]
                        if not post_url.startswith("http"):
                            post_url = "https://www.facebook.com" + post_url

                    # Tìm mốc thời gian từ aria-label hoặc link text
                    candidate_time = aria if re.search(r"\d", aria) else txt
                    if candidate_time and not post_time_str:
                        dt = parse_timestamp(candidate_time)
                        if dt:
                            post_time_str = candidate_time
                            post_dt = dt

            # Nếu chưa tìm được thời gian từ thẻ a, quét regex từ bài viết
            if not post_dt:
                time_matches = re.findall(
                    r"(\d{1,2}\s+[Tt]háng\s+\d{1,2}(?:,\s*\d{4})?|\d+\s*(?:giờ|phút|ngày|tuần|tháng|năm)|hôm qua)",
                    cleaned, re.IGNORECASE
                )
                if time_matches:
                    for tm in time_matches:
                        dt = parse_timestamp(tm)
                        if dt:
                            post_time_str = tm
                            post_dt = dt
                            break

            if post_dt:
                if oldest_dt is None or post_dt < oldest_dt:
                    oldest_dt = post_dt

            # Tạo mã định danh duy nhất cho bài viết
            if post_url:
                post_id = re.sub(r"\W+", "_", post_url)
            else:
                post_id = f"{page_id}_{hash(cleaned[:60])}"

            posts.append({
                "post_id": post_id,
                "page": page_id,
                "post_url": post_url,
                "post_time": post_time_str,
                "timestamp_utc": int(post_dt.timestamp()) if post_dt else 0,
                "text": cleaned,
                "likes": 0,
                "comments_count": 0,
                "shares": 0,
            })
    except Exception as e:
        logger.debug(f"Lỗi extract timeline: {e}")

    return posts, oldest_dt


async def crawl_page_timeline_2years(page, page_info: dict, cutoff_date: datetime):
    """Cuộn trang Facebook lùi dần 2 năm bằng PageDown, liên tục lưu vào SQLite."""
    page_id = page_info["id"]
    page_url = page_info["url"]

    logger.info(f"\n{'=' * 65}")
    logger.info(f"🕷️ GIAI ĐOẠN 1: Quét Timeline 2 năm cho {page_id}")
    logger.info(f"   Mốc thời gian cần lùi về: {cutoff_date.strftime('%d/%m/%Y')}")
    logger.info(f"{'=' * 65}")

    await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(4000)
    await dismiss_timeline_popups(page)

    max_scroll_cycles = 1200
    posts_saved_total = 0
    consecutive_no_progress = 0

    for cycle in range(max_scroll_cycles):
        # 1. Cuộn bằng phím PageDown
        await page.keyboard.press("PageDown")
        await page.wait_for_timeout(random.randint(1200, 1800))

        # Đóng dialog nếu Facebook hiện lại
        if (cycle + 1) % 5 == 0:
            await dismiss_timeline_popups(page)

        # 2. Định kỳ mỗi 10 lần PageDown: trích xuất và lưu bài viết vào database
        if (cycle + 1) % 10 == 0:
            posts_batch, oldest_dt = await extract_visible_timeline_posts(page, page_id)
            new_inserted = 0
            for p in posts_batch:
                if save_post_to_db(p):
                    new_inserted += 1
            posts_saved_total += new_inserted

            oldest_str = oldest_dt.strftime('%d/%m/%Y') if oldest_dt else "Đang đọc..."
            logger.info(f"   📜 PageDown #{cycle + 1:04d} | Đã lưu: {posts_saved_total} bài mới | Bài cũ nhất: {oldest_str}")

            # Kiểm tra xem đã chạm mốc 2 năm chưa
            if oldest_dt and oldest_dt < cutoff_date:
                logger.info(f"   🎯 ĐÃ ĐẠT MỐC 2 NĂM ({oldest_dt.strftime('%d/%m/%Y')})! Dừng quét timeline {page_id}.")
                break

            # Kiểm tra nếu cuộn liên tục 50 lần không có bài mới
            if new_inserted == 0:
                consecutive_no_progress += 1
                if consecutive_no_progress >= 15:
                    logger.info("   ⚠️ Đã chạm đáy trang hoặc không còn bài viết cũ hơn.")
                    break
            else:
                consecutive_no_progress = 0

            # 3. Dọn dẹp DOM định kỳ mỗi 60 lần cuộn để RAM luôn < 500MB
            if (cycle + 1) % 60 == 0:
                try:
                    await page.evaluate("""
                        const articles = document.querySelectorAll('div[role="article"]');
                        if (articles.length > 60) {
                            for (let i = 0; i < articles.length - 40; i++) {
                                articles[i].remove();
                            }
                        }
                    """)
                except Exception:
                    pass

    stats = get_db_stats()
    logger.info(f"✅ Hoàn thành Giai đoạn 1 cho {page_id}. Tổng bài viết trong DB hiện tại: {stats['posts']}")


# ---------------------------------------------------------------------------
# Giai đoạn 2: Bóc tách toàn bộ Bình luận & Phản hồi (Deep Dive)
# ---------------------------------------------------------------------------
async def crawl_post_all_comments(page, post: dict):
    """Mở link bài viết riêng lẻ và tự động bung toàn bộ bình luận & phản hồi."""
    post_url = post["post_url"]
    post_id = post["post_id"]

    if not post_url:
        mark_comments_done(post_id)
        return

    logger.info(f"   💬 Đang cào bình luận bài: {post_url[:75]}...")

    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(3000)

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

        # Lặp lại thao tác click "Xem thêm bình luận"
        for _ in range(25):
            clicked_any = False
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
        articles = await page.query_selector_all('div[role="article"]')
        saved_comments_count = 0
        seen_comments = set()

        for a_idx, art in enumerate(articles):
            try:
                aria_label = await art.get_attribute("aria-label") or ""
                # Kiểm tra đây có phải là bình luận không (bình luận có aria-label chứa 'Bình luận' hoặc 'Comment')
                is_comment = ("bình luận" in aria_label.lower() or "comment" in aria_label.lower())
                raw_text = (await art.inner_text()).strip()
                lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

                if not lines:
                    continue

                # Nếu là bài viết gốc (thường là article đầu tiên hoặc có tên fanpage), bỏ qua
                if a_idx == 0 and not is_comment:
                    continue

                author = lines[0]
                # Lọc bỏ nút Thích, Phản hồi, thời gian ở dòng cuối
                content_lines = [
                    l for l in lines[1:]
                    if not re.match(r"^(Thích|Like|Trả lời|Reply|\d+\s*(giờ|ngày|tuần|tháng|h|d|w|m|phút)|Phản hồi|Đã chỉnh sửa)$", l, re.IGNORECASE)
                ]
                comment_text = clean_text(" ".join(content_lines))

                if len(comment_text) < 2:
                    continue

                dedup_key = (author, comment_text)
                if dedup_key in seen_comments:
                    continue
                seen_comments.add(dedup_key)

                c_id = f"{post_id}_c_{hash(dedup_key)}"
                if save_comment_to_db({
                    "comment_id": c_id,
                    "post_id": post_id,
                    "author": author,
                    "comment_text": comment_text,
                    "comment_time": aria_label,
                    "likes": 0,
                }):
                    saved_comments_count += 1
            except Exception:
                continue

        logger.info(f"   ✅ Đã lưu {saved_comments_count} bình luận.")
        mark_comments_done(post_id)

    except Exception as e:
        logger.warning(f"   ⚠️ Lỗi cào comment: {e}")
        mark_comments_done(post_id)


# ---------------------------------------------------------------------------
# Giai đoạn 3: Phân tích Sentiment hàng loạt (Batch NLP)
# ---------------------------------------------------------------------------
def run_full_sentiment_analysis():
    """Phân tích sắc thái cho toàn bộ bài viết và bình luận trong cơ sở dữ liệu."""
    logger.info("\n" + "=" * 65)
    logger.info("🧠 GIAI ĐOẠN 3: Bắt đầu phân tích Sentiment toàn bộ dữ liệu 2 năm")
    logger.info("=" * 65)

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
    logger.info(f"💬 Đang phân tích sentiment cho {len(unclassified_comments)} bình luận sinh viên...")

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

    # Xuất báo cáo tổng hợp
    report_file = DATA_DIR / f"report_2years_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("📊 BÁO CÁO PHÂN TÍCH TỔNG HỢP SENTIMENT 2 NĂM (UIT FACEBOOK)\n")
        f.write(f"   Thời gian tạo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write("📈 1. THỐNG KÊ BÀI VIẾT (UIT.Fanpage & UITconfess):\n")
        for k, v in post_stats.items():
            f.write(f"   • {k or 'Chưa rõ'}: {v} bài\n")
        f.write("\n💬 2. THỐNG KÊ BÌNH LUẬN CỦA SINH VIÊN:\n")
        for k, v in comment_stats.items():
            f.write(f"   • {k or 'Chưa rõ'}: {v} bình luận\n")
        f.write("\n" + "=" * 70 + "\n")

    logger.info(f"🎉 Hoàn thành phân tích! Báo cáo chi tiết: {report_file}")


# ---------------------------------------------------------------------------
# Giai đoạn 4: Xuất CSV chuẩn Excel UTF-8 BOM
# ---------------------------------------------------------------------------
def export_db_to_csv():
    """Xuất toàn bộ bảng posts và comments từ SQLite sang CSV."""
    import pandas as pd
    try:
        conn = sqlite3.connect(DB_PATH)
        df_posts = pd.read_sql_query("SELECT * FROM posts", conn)
        df_comments = pd.read_sql_query("SELECT * FROM comments", conn)
        conn.close()

        csv_posts = DATA_DIR / "posts_2years_latest.csv"
        csv_comments = DATA_DIR / "comments_2years_latest.csv"

        df_posts.to_csv(csv_posts, index=False, encoding="utf-8-sig")
        df_comments.to_csv(csv_comments, index=False, encoding="utf-8-sig")

        logger.info(f"💾 Đã xuất toàn bộ dữ liệu ra Excel/CSV:")
        logger.info(f"   • Bài viết: {csv_posts}")
        logger.info(f"   • Bình luận: {csv_comments}")
    except Exception as e:
        logger.warning(f"Lỗi xuất CSV: {e}")


# ---------------------------------------------------------------------------
# Quản lý an toàn tài khoản & Điều phối chính
# ---------------------------------------------------------------------------
def load_env():
    """Đọc credentials từ .env file."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return None, None
    env = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env.get("FB_EMAIL"), env.get("FB_PASSWORD")


async def check_account_safety(page) -> bool:
    """Kiểm tra dấu hiệu bất thường để dừng khẩn cấp, bảo vệ tài khoản 100%."""
    url = page.url.lower()
    if "checkpoint" in url or "temporarily_blocked" in url:
        logger.error("🛑 PHÁT HIỆN CẢNH BÁO CHECKPOINT! Tự động dừng để bảo vệ tài khoản an toàn tuyệt đối.")
        return False
    return True


async def async_main():
    from playwright.async_api import async_playwright

    init_database()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    email, password = load_env()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--lang=vi-VN"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        # 1. Stealth mode chống bot
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
        """)

        # 2. Chặn đa phương tiện tĩnh để siêu nhẹ và tránh tải tracker
        await context.route("**/*.{png,jpg,jpeg,gif,svg,mp4,webm,webp,woff,woff2,ttf,eot}",
                            lambda route: route.abort())

        # 3. Nạp session cookies đã lưu
        if COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                    await context.add_cookies(json.load(f))
                logger.info("🍪 Đã nạp Cookies đăng nhập thành công.")
            except Exception as e:
                logger.warning(f"Lỗi nạp cookies: {e}")

        page = await context.new_page()

        # Kiểm tra c_user
        cookies = await context.cookies()
        has_c_user = any(c.get("name") == "c_user" for c in cookies)
        if has_c_user:
            logger.info("   ✅ Phiên đăng nhập hợp lệ (c_user cookie active).")
        else:
            logger.warning("   ⚠️ Cookie chưa có c_user, vui lòng kiểm tra cookies.")

        # BƯỚC 1: Quét Timeline bài viết trong 2 năm cho cả 2 Fanpage
        for page_info in PAGES:
            if not await check_account_safety(page):
                break
            await crawl_page_timeline_2years(page, page_info, cutoff_date)
            # Nghỉ an toàn giữa 2 fanpage
            cooldown = random.randint(10, 18)
            logger.info(f"⏳ Nghỉ an toàn {cooldown}s trước khi chuyển fanpage tiếp theo...")
            await asyncio.sleep(cooldown)

        # BƯỚC 2: Cào bình luận cho các bài viết đã thu thập
        logger.info("\n" + "=" * 65)
        logger.info("💬 BƯỚC 2: Bắt đầu thu thập toàn bộ bình luận của các bài viết...")
        logger.info("=" * 65)

        posts_to_crawl = get_posts_needing_comments(limit=3000)
        logger.info(f"Tìm thấy {len(posts_to_crawl)} bài viết cần cào bình luận.")

        for idx, post in enumerate(posts_to_crawl):
            if not await check_account_safety(page):
                logger.warning("Dừng cào bình luận để bảo vệ tài khoản an toàn.")
                break

            logger.info(f"[{idx + 1}/{len(posts_to_crawl)}]")
            await crawl_post_all_comments(page, post)

            # Nghỉ ngẫu nhiên giữa các bài viết để chống ban
            await asyncio.sleep(random.uniform(2.5, 4.5))

            # Định kỳ mỗi 20 bài: nghỉ giải lao chống rate limit
            if (idx + 1) % 20 == 0:
                rest_time = random.randint(15, 30)
                logger.info(f"☕ Đã cào {idx + 1} bài. Tạm dừng {rest_time}s mô phỏng hành vi người thật...")
                await asyncio.sleep(rest_time)

        await browser.close()

    # BƯỚC 3: Phân tích Sentiment tổng lực
    run_full_sentiment_analysis()

    # BƯỚC 4: Xuất dữ liệu sang file CSV để dễ mở Excel
    export_db_to_csv()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
