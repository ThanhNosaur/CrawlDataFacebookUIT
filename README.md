# Facebook UIT Scraper & Sentiment Analyzer (Hệ Thống 2 Năm Đầy Đủ)

Hệ thống tự động thu thập toàn bộ dữ liệu bài viết và bình luận trong **2 năm (730 ngày)** từ 2 fanpage chính thức của **Trường Đại học Công nghệ Thông tin - ĐHQG TP.HCM (UIT)**:
1. **UIT Fanpage**: [https://www.facebook.com/UIT.Fanpage](https://www.facebook.com/UIT.Fanpage)
2. **UIT Confessions**: [https://www.facebook.com/UITconfess](https://www.facebook.com/UITconfess)

---

## 📌 1. KẾT QUẢ ĐƯỢC LƯU Ở ĐÂU?

Tất cả kết quả xử lý, phân loại và cơ sở dữ liệu được tổ chức tại thư mục [`data/`](data/):

| Tên file kết quả | Định dạng | Nội dung chi tiết |
| :--- | :---: | :--- |
| **`data/fb_uit_2years.db`** | **SQLite Database** | **Cơ sở dữ liệu cốt lõi lưu trữ lũy tiến**: Bảng `posts` (toàn bộ bài viết 2 năm) và bảng `comments` (toàn bộ bình luận & phản hồi). Cho phép tắt máy mở lại cào tiếp (Resume) không bao giờ mất dữ liệu. |
| **`data/posts_2years_latest.csv`** | **Excel / CSV (UTF-8 BOM)** | Toàn bộ bài viết trong 2 năm gồm link, nội dung, ngày giờ, số like/cmt, và nhãn phân loại cảm xúc (`positive`, `negative`, `neutral`). Mở trực tiếp trên Microsoft Excel không bị lỗi font tiếng Việt. |
| **`data/comments_2years_latest.csv`** | **Excel / CSV (UTF-8 BOM)** | Toàn bộ bình luận & phản hồi của sinh viên, người bình luận, thời gian, và kết quả phân tích cảm xúc từng câu bình luận. |
| **`data/report_2years_*.txt`** | **Báo cáo Thống kê** | Báo cáo định lượng tỷ lệ Tích cực / Tiêu cực / Trung lập của sinh viên và người theo dõi UIT trong suốt 2 năm qua. |
| **`data/classified_posts_latest.csv`** | **CSV** | Dữ liệu mẫu bài viết gần đây kèm các từ khóa khen/chê nhận diện được (`matched_keywords`). |
| **`data/classified_posts_latest.json`** | **JSON** | Dữ liệu định dạng JSON để tích hợp API hoặc web visualization. |

---

## 🚀 2. CÁCH KHỞI CHẠY HỆ THỐNG

### Bước 1: Cài đặt môi trường
```bash
py -m pip install -r requirements.txt
py -m playwright install chromium
```

### Bước 2: Chạy hệ thống thu thập 2 năm (Đầy đủ Bài viết + Bình luận + Phân tích)
```bash
py main.py 2years
```
*Hệ thống sẽ tự động thực hiện 4 giai đoạn:*
1. **Giai đoạn 1 (Timeline Harvest)**: Tự động cuộn lùi thời gian đến đúng mốc 2 năm (730 ngày) trên cả 2 trang `UIT.Fanpage` và `UITconfess`, bóc tách từng bài viết vào database SQLite.
2. **Giai đoạn 2 (Deep Comment Expansion)**: Mở từng bài viết, bấm "Xem thêm bình luận" và mở toàn bộ các phản hồi con lồng nhau (Replies), lưu trữ vào bảng `comments`.
3. **Giai đoạn 3 (Batch Sentiment Analysis)**: Áp dụng thuật toán Hybrid NLP (`underthesea` + UIT Lexicon) để gắn nhãn tích cực / tiêu cực / trung lập cho mọi bài viết và bình luận.
4. **Giai đoạn 4 (Export Report & CSV)**: Xuất dữ liệu ra file CSV tương thích Excel và tạo báo cáo thống kê.

### Các lệnh chạy khác:
```bash
py main.py            # Chạy pipeline cơ bản
py main.py scrape     # Chỉ cào bài viết gần đây
py main.py analyze    # Chỉ chạy phân tích sentiment trên database hiện có
```

---

## 🛡️ 3. CƠ CHẾ BẢO VỆ CHỐNG BAN TÀI KHOẢN (ANTI-BAN SYSTEM)

Hệ thống được thiết kế theo chuẩn **Human Mimicry & Zero Risk Detection**:

1. **Bảo mật Credentials tuyệt đối**:
   - Tài khoản đăng nhập được lưu duy nhất trong file `.env` nội bộ trên máy bạn.
   - Session Cookies lưu tại `cookies/fb_cookies.json`.
   - Cả hai file trên cùng toàn bộ file `.db` đều nằm trong `.gitignore`, **tuyệt đối không bao giờ bị đưa lên GitHub**.

2. **Playwright Undetected Stealth**:
   - Vô hiệu hóa `navigator.webdriver`.
   - Giả lập đầy đủ `plugins`, `languages`, `chrome.runtime`.
   - Vô hiệu hóa tải hình ảnh / media tĩnh để tăng tốc x10 lần và triệt tiêu các pixel theo dõi (tracking pixels) của Meta.

3. **Human Timing & Smart Jitter (Nhịp độ người thật)**:
   - Cuộn bằng phím `PageDown` mượt mà, giãn cách ngẫu nhiên `1.2s - 2.5s` mỗi lần cuộn.
   - Giữa các bài viết khi cào bình luận: nghỉ ngẫu nhiên `2.5s - 4.5s`.
   - Nghỉ giải lao chống Rate Limit: Mỗi 20 bài viết, hệ thống tự động nghỉ `15s - 30s`.
   - Nghỉ an toàn giữa 2 fanpage `10s - 20s`.

4. **Bộ ngắt khẩn cấp tự động (Auto-Checkpoint Shield)**:
   - Trong từng vòng lặp, hệ thống tự động kiểm tra URL. Nếu Facebook có bất kỳ dấu hiệu yêu cầu xác minh (`checkpoint` hoặc `temporarily_blocked`), hệ thống sẽ **ngay lập tức dừng chương trình**, bảo vệ an toàn 100% cho tài khoản Facebook.

5. **DOM Memory Recycling (Chống tràn RAM)**:
   - Cơ chế tự động dọn bớt các phần tử bài viết đã cuộn qua khi số lượng vượt quá 60 node, giữ cho tiến trình Playwright luôn tiêu thụ dưới `500MB RAM`, hoạt động liên tục nhiều giờ không lo crash trình duyệt.

---

## 🧠 4. PHƯƠNG PHÁP PHÂN TÍCH CẢM XÚC (HYBRID MODEL)

Điểm cảm xúc được xác định theo mô hình lai 2 tầng:

$$\text{Final Score} = (\text{NLP Score} \times 0.6) + (\text{Keyword Score} \times 0.4)$$

1. **Lớp 1 - Mô hình NLP `underthesea` (60%)**:
   - Tách từ ngữ tiếng Việt và phân tích cú pháp biểu cảm tổng quát (`positive` / `negative` / `neutral`).
2. **Lớp 2 - Bộ từ điển đặc thù UIT (40%)**:
   - **Tích cực**: Khen giảng viên tận tâm, chương trình tiên tiến, trao đổi quốc tế (Singapore, AvePoint), học bổng, việc làm công nghệ cao, áo khoa đẹp, đồ án xuất sắc...
   - **Tiêu cực**: Phàn nàn rớt môn, nợ môn, gánh team bài tập nhóm, deadline dồn dập, học phí tăng, phòng máy lạnh hỏng...
