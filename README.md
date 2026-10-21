# Facebook UIT Scraper & Sentiment Analyzer (Hệ Thống 2 Năm Đầy Đủ)

Hệ thống tự động thu thập toàn bộ dữ liệu bài viết và bình luận trong **2 năm (730 ngày)** từ 2 fanpage chính thức của **Trường Đại học Công nghệ Thông tin - ĐHQG TP.HCM (UIT)**:
1. **UIT Fanpage**: [https://www.facebook.com/UIT.Fanpage](https://www.facebook.com/UIT.Fanpage) (Kênh thông tin chính thức của nhà trường)
2. **UIT Confessions**: [https://www.facebook.com/UITconfess](https://www.facebook.com/UITconfess) (Diễn đàn tâm tư, ý kiến sinh viên)

---

## 📊 1. KẾT QUẢ THỐNG KÊ PHÂN TÍCH SENTIMENT 2 NĂM

Dữ liệu đã thu thập và xử lý toàn diện qua thuật toán **Hybrid NLP (`underthesea` + UIT Keyword Lexicon)**:

### 📈 Bảng Tổng Hợp Số Liệu:

| Hạng Mục | Tổng Số Lượng | ✅ Tích Cực (Positive) | ⚪ Trung Lập (Neutral) | ❌ Tiêu Cực (Negative) |
| :--- | :---: | :---: | :---: | :---: |
| **Bài viết & Confession** | **560 bài** | **225 bài** (40.2%) | **296 bài** (52.9%) | **39 bài** (7.0%) |
| **Bình luận của sinh viên** | **4.773 bình luận** | **1.633 bình luận** (34.2%) | **2.307 bình luận** (48.3%) | **833 bình luận** (17.5%) |

### 🔍 Phân Tích Chi Tiết Nội Dung Cảm Xúc:

1. **Về Bài Viết & Confession (560 bài):**
   - **Tích Cực (40.2% - 225 bài):** Chiếm ưu thế lớn từ các bài đăng trên Fanpage chính thức về sự kiện quốc tế (hợp tác doanh nghiệp Singapore, AvePoint), ngày hội chào đón tân sinh viên, vinh danh thủ khoa, trao học bổng doanh nghiệp, giải thưởng Olympic tin học và các thành tích nghiên cứu khoa học xuất sắc.
   - **Trung Lập (52.9% - 296 bài):** Chủ yếu là các thông báo học vụ, lịch thi, đăng ký học phần, tin tuyển dụng việc làm thực tập UIT Career Day, quy trình xét điểm rèn luyện và sinh hoạt công dân.
   - **Tiêu Cực (7.0% - 39 bài):** Các bài confession sinh viên chia sẻ áp lực thi cử cuối kỳ, quá tải đồ án chuyên ngành, các bất đồng khi làm bài tập nhóm hoặc tâm sự về việc chọn sai ngành.

2. **Về Bình Luận & Phản Hồi Sinh Viên (4.773 bình luận):**
   - **Tích Cực (34.2% - 1.633 bình luận):** Sinh viên hào hứng tag bạn bè khi có tên trên bảng vinh danh, cảm ơn thầy cô hỗ trợ hướng dẫn khóa luận tốt nghiệp, khen áo khoa/áo sự kiện đẹp, bày tỏ niềm tự hào về trường.
   - **Trung Lập (48.3% - 2.307 bình luận):** Tag bạn bè nhắc lịch học, hỏi xin tài liệu ôn thi, hỏi thăm phòng thi, tìm đồ thất lạc tại sảnh trường hoặc thảo luận thông tin tuyển dụng.
   - **Tiêu Cực (17.5% - 833 bình luận):** Phản ánh sinh động góc nhìn sinh viên: phàn nàn về tình trạng "gánh team" bài tập nhóm, deadline dồn dập, lo lắng nguy cơ nợ môn/học lại, học phí hoặc phản biện các ý kiến trên confession.

---

## 📌 2. KẾT QUẢ ĐƯỢC LƯU Ở ĐÂU?

Tất cả kết quả xử lý, phân loại và cơ sở dữ liệu được tổ chức tại thư mục [`data/`](data/):

| Tên file kết quả | Định dạng | Nội dung chi tiết |
| :--- | :---: | :--- |
| **`data/posts_2years_latest.csv`** | **Excel / CSV (UTF-8 BOM)** | Toàn bộ **560 bài viết** trong 2 năm gồm link permalink, nội dung, ngày giờ, số like/cmt, và nhãn phân loại cảm xúc (`positive`, `negative`, `neutral`). Mở trực tiếp trên Microsoft Excel không bị lỗi font tiếng Việt. |
| **`data/comments_2years_latest.csv`** | **Excel / CSV (UTF-8 BOM)** | Toàn bộ **4.773 bình luận** của sinh viên (tác giả, nội dung comment, thời gian, nhãn sentiment, điểm số cảm xúc). |
| **`data/report_2years_20261021_101844.txt`** | **Báo cáo Thống kê** | Báo cáo định lượng chi tiết tổng kết tỷ lệ Tích cực / Tiêu cực / Trung lập của sinh viên UIT trong suốt 2 năm qua. |
| **`data/fb_uit_2years.db`** | **SQLite Database** | **Cơ sở dữ liệu cốt lõi lưu trữ lũy tiến**: Bảng `posts` (560 bài) và bảng `comments` (4.773 bình luận). Cho phép tắt máy mở lại cào tiếp (Resume) không bao giờ mất dữ liệu hay cào trùng lặp. |

---

## 🚀 3. CÁCH KHỞI CHẠY HỆ THỐNG

### Bước 1: Cài đặt môi trường
```bash
py -m pip install -r requirements.txt
py -m playwright install chromium
```

### Bước 2: Chạy hệ thống thu thập 2 năm (Đầy đủ Bài viết + Bình luận + Phân tích)
```bash
py main.py
```
*Hệ thống sẽ tự động thực hiện 4 giai đoạn:*
1. **Giai đoạn 1 (Timeline Harvest)**: Tự động cuộn lùi thời gian đến đúng mốc 2 năm (730 ngày) trên cả 2 trang `UIT.Fanpage` và `UITconfess`, bóc tách từng bài viết vào database SQLite.
2. **Giai đoạn 2 (Deep Comment Expansion)**: Mở từng bài viết, bấm "Xem thêm bình luận" và mở toàn bộ các phản hồi con lồng nhau (Replies), lưu trữ vào bảng `comments`.
3. **Giai đoạn 3 (Batch Sentiment Analysis)**: Áp dụng thuật toán Hybrid NLP (`underthesea` + UIT Lexicon) để gắn nhãn tích cực / tiêu cực / trung lập cho mọi bài viết và bình luận.
4. **Giai đoạn 4 (Export Report & CSV)**: Xuất dữ liệu ra file CSV tương thích Excel và tạo báo cáo thống kê.

### Các lệnh chạy khác:
```bash
py main.py 2years     # Cào toàn bộ 2 năm bài viết và bình luận
py main.py analyze    # Chỉ chạy phân tích sentiment trên database hiện có
py main.py export     # Chỉ xuất database SQLite ra file CSV Excel
```

---

## 🛡️ 4. CƠ CHẾ BẢO VỆ CHỐNG BAN TÀI KHOẢN (ANTI-BAN SYSTEM)

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
   - Cuộn phối hợp đồng thời cả `#scrollview`, `window`, phím `PageDown` và `mouse.wheel`, giãn cách ngẫu nhiên `1.2s - 2.5s` mỗi lần cuộn.
   - Giữa các bài viết khi cào bình luận: nghỉ ngẫu nhiên `2.0s - 3.5s`.
   - Nghỉ giải lao chống Rate Limit: Mỗi 25 bài viết, hệ thống tự động nghỉ `10s - 20s`.
   - Nghỉ an toàn giữa 2 fanpage `8s - 15s`.

4. **Bộ ngắt khẩn cấp tự động (Auto-Checkpoint Shield)**:
   - Trong từng vòng lặp, hệ thống tự động kiểm tra URL. Nếu Facebook có bất kỳ dấu hiệu yêu cầu xác minh (`checkpoint` hoặc `temporarily_blocked`), hệ thống sẽ **ngay lập tức dừng chương trình**, bảo vệ an toàn 100% cho tài khoản Facebook.

5. **DOM Memory Recycling & Virtual Scroll Capture**:
   - Bắt và lưu bài viết ngay trong DOM hiện tại trước khi cơ chế Virtual DOM của Facebook unmount, giữ RAM luôn `< 500MB`.

---

## 🧠 5. PHƯƠNG PHÁP PHÂN TÍCH CẢM XÚC (HYBRID MODEL)

Điểm cảm xúc được xác định theo mô hình lai 2 tầng:

$$\text{Final Score} = (\text{NLP Score} \times 0.6) + (\text{Keyword Score} \times 0.4)$$

1. **Lớp 1 - Mô hình NLP `underthesea` (60%)**:
   - Tách từ ngữ tiếng Việt và phân tích cú pháp biểu cảm tổng quát (`positive` / `negative` / `neutral`).
2. **Lớp 2 - Bộ từ điển đặc thù UIT (40%)**:
   - **Tích cực**: Khen giảng viên tận tâm, chương trình tiên tiến, trao đổi quốc tế (Singapore, AvePoint), học bổng, việc làm công nghệ cao, áo khoa đẹp, đồ án xuất sắc...
   - **Tiêu cực**: Phàn nàn rớt môn, nợ môn, gánh team bài tập nhóm, deadline dồn dập, học phí tăng, phòng máy lạnh hỏng...
