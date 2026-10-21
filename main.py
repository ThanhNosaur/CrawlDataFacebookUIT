# -*- coding: utf-8 -*-
"""
=============================================================================
Facebook UIT Scraper & Sentiment Analyzer - Main Entrypoint
=============================================================================
Cách sử dụng:
    py main.py            # Chạy toàn bộ pipeline (Crawl bài viết 2 năm, comment, sentiment, export)
    py main.py 2years      # Cào toàn bộ 2 năm bài viết và bình luận
    py main.py analyze    # Chỉ chạy phân tích sentiment trên database hiện có
    py main.py export     # Xuất dữ liệu từ SQLite sang Excel CSV
    py main.py install    # Cài đặt thư viện dependencies
    py main.py help       # Hiện hướng dẫn sử dụng
=============================================================================
"""

import subprocess
import sys
from pathlib import Path


def install_requirements():
    """Cài đặt thư viện từ requirements.txt."""
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("❌ Không tìm thấy requirements.txt")
        return False
    
    print("📦 Đang kiểm tra và cài đặt thư viện...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    if result.returncode != 0:
        print("⚠️ Một số thư viện chưa cài được, hãy thử chạy: pip install -r requirements.txt")
        return False
    print("✅ Thư viện đã sẵn sàng!\n")
    return True


def run_full_pipeline():
    """Chạy toàn bộ pipeline 2 năm."""
    print("\n" + "=" * 65)
    print("🚀 BẮT ĐẦU PIPELINE THU THẬP & PHÂN TÍCH SENTIMENT UIT (2 NĂM)")
    print("=" * 65 + "\n")
    import scraper_full_2years
    scraper_full_2years.main()


def run_sentiment_only():
    """Chỉ chạy phân tích sentiment trên database hiện có."""
    print("\n" + "=" * 65)
    print("🧠 CHẠY PHÂN TÍCH SENTIMENT TRÊN DỮ LIỆU HIỆN CÓ")
    print("=" * 65 + "\n")
    import scraper_full_2years
    scraper_full_2years.run_full_sentiment_analysis()
    scraper_full_2years.export_db_to_csv()


def export_only():
    """Chỉ xuất SQLite ra CSV."""
    print("\n" + "=" * 65)
    print("💾 XUẤT CƠ SỞ DỮ LIỆU RA CSV")
    print("=" * 65 + "\n")
    import scraper_full_2years
    scraper_full_2years.export_db_to_csv()


def show_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║        FACEBOOK UIT SCRAPER & SENTIMENT ANALYZER             ║
╠══════════════════════════════════════════════════════════════╣
║  Lệnh chạy:                                                  ║
║    py main.py            Chạy toàn bộ quy trình 2 năm        ║
║    py main.py 2years     Chạy cào 2 năm + bình luận          ║
║    py main.py analyze    Chỉ phân tích sentiment trên DB     ║
║    py main.py export     Chỉ xuất file CSV ra Excel          ║
║    py main.py install    Cài đặt dependencies                ║
║    py main.py help       Hiện hướng dẫn                      ║
║                                                              ║
║  Dữ liệu đầu ra:                                             ║
║    data/fb_uit_2years.db           Cơ sở dữ liệu SQLite      ║
║    data/posts_2years_latest.csv    Bài viết kèm Sentiment    ║
║    data/comments_2years_latest.csv Bình luận kèm Sentiment   ║
║    data/report_2years_*.txt        Báo cáo thống kê tổng kết ║
╚══════════════════════════════════════════════════════════════╝
    """)


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    command = args[0].lower() if args else "all"

    if command == "help":
        show_help()
        return
    if command == "install":
        install_requirements()
        return

    if command in ["all", "2years", "full"]:
        run_full_pipeline()
    elif command == "analyze":
        run_sentiment_only()
    elif command == "export":
        export_only()
    else:
        print(f"❌ Lệnh không hợp lệ: {command}")
        show_help()


if __name__ == "__main__":
    main()
