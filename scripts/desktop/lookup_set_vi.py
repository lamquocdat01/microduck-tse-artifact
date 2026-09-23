"""Nửa TIẾNG VIỆT của bộ thử định tuyến tra cứu — dựng native, không dịch FreshQA.

Vì sao không dịch: một câu `fast-changing` của Mỹ dịch sang tiếng Việt vẫn là câu
hỏi về nước Mỹ. Nó đo khả năng đọc tiếng Việt, không đo được gì về ngữ cảnh Việt
Nam. Giao thức đầy đủ: `docs/benchmark/LABELING-PROTOCOL.md` §5.

Ba `fact_type` theo đúng định nghĩa FreshQA (Vu et al., Findings of ACL 2024):

    never-changing   đáp án tĩnh
    slow-changing    đáp án đổi trong vài năm      -> ca ranh giới
    fast-changing    đáp án đổi trong vài ngày/tuần

`FALSE_PREMISE_VI` là khối B: câu hỏi khẳng định sẵn một điều sai. Hành vi đúng là
PHẢN BÁC, không phải tra cứu — nên `needs_lookup` của khối này không chấm.

Gán bởi MỘT người duy nhất, 09/09/2026. Không có lượt gán thứ hai, không có
Cohen's kappa. Đó là hạn chế đã ghi trong giao thức §6, không phải chỗ bỏ sót.
"""

from __future__ import annotations

# -- never-changing: đáp án tĩnh, vịt biết chắc, KHÔNG cần tra ----------------
NEVER_CHANGING_VI: list[str] = [
    "Sông nào dài nhất Việt Nam?",
    "Chiến dịch Điện Biên Phủ kết thúc vào năm nào?",
    "Vua Quang Trung tên thật là gì?",
    "Việt Nam có bao nhiêu tỉnh giáp biên giới với Lào?",
    "Đỉnh núi cao nhất Việt Nam tên gì và cao bao nhiêu mét?",
    "Nước sôi ở bao nhiêu độ C khi ở áp suất khí quyển tiêu chuẩn?",
    "Hai mũ hai mươi bằng bao nhiêu?",
    "Quang hợp là quá trình gì?",
    "Trong Python thì list khác tuple ở chỗ nào?",
    "Giao thức TCP khác UDP ở điểm nào?",
    "Truyện Kiều do ai sáng tác?",
    "Áo dài Việt Nam gồm những bộ phận nào?",
    "Vì sao bầu trời ban ngày có màu xanh?",
    "Dịch câu 'the early bird catches the worm' sang tiếng Việt.",
    "Một năm nhuận có bao nhiêu ngày và vì sao lại có năm nhuận?",
    "Chữ Quốc ngữ được xây dựng dựa trên bảng chữ cái nào?",
    "Hồ Hoàn Kiếm nằm ở quận nào của Hà Nội?",
    "Định lý Pythagore phát biểu thế nào?",
    "Vịnh Hạ Long được UNESCO công nhận là di sản thiên nhiên thế giới năm nào?",
    "Phở bò truyền thống gồm những nguyên liệu chính nào?",
    "Bộ nhớ RAM khác ổ cứng SSD ở điểm căn bản nào?",
    "Nguyễn Trãi viết Bình Ngô đại cáo trong hoàn cảnh nào?",
    "Một hải lý bằng bao nhiêu mét?",
    "Vì sao nước biển mặn?",
    "Hệ điều hành Linux ra đời năm nào và do ai khởi xướng?",
]

# -- slow-changing: đổi trong vài năm — ca RANH GIỚI, giữ lại ------------------
SLOW_CHANGING_VI: list[str] = [
    "Dân số Việt Nam hiện nay khoảng bao nhiêu người?",
    "Việt Nam hiện có bao nhiêu tỉnh và thành phố trực thuộc trung ương?",
    "Ai đang là chủ tịch nước Việt Nam?",
    "Trường đại học nào ở Việt Nam đứng đầu bảng xếp hạng trong nước?",
    "Tuổi nghỉ hưu của lao động nam ở Việt Nam hiện là bao nhiêu?",
    "Sân bay Long Thành đã đi vào hoạt động chưa?",
    "Mức lương cơ sở của công chức Việt Nam hiện là bao nhiêu?",
    "Việt Nam đã ký bao nhiêu hiệp định thương mại tự do?",
    "Tuyến metro nào ở Thành phố Hồ Chí Minh đang chạy?",
    "Hiện có bao nhiêu di sản thế giới của Việt Nam được UNESCO công nhận?",
]

# -- fast-changing: đổi trong vài ngày/tuần — CẦN tra ------------------------
FAST_CHANGING_VI: list[str] = [
    "Năm nay Đại học Khoa học Tự nhiên tuyển sinh tiến sĩ thế nào?",   # ca đã hỏng thật
    "Giá vàng SJC hôm nay bao nhiêu một lượng?",
    "Tỷ giá đô la Mỹ sang tiền Việt hôm nay là bao nhiêu?",
    "Ngày mai Hà Nội có mưa không?",
    "Giá xăng RON 95 trong nước hiện là bao nhiêu một lít?",
    "Tuần rồi có tin gì đáng chú ý về trí tuệ nhân tạo ở Việt Nam?",
    "Vé máy bay Hà Nội – Đà Nẵng tuần sau khoảng bao nhiêu tiền?",
    "Đội tuyển Việt Nam đá trận gần nhất với tỉ số bao nhiêu?",
    "Chỉ số VN-Index đóng cửa phiên hôm nay ở mức nào?",
    "Hạn nộp hồ sơ xét tuyển đại học đợt này là ngày nào?",
    "Phiên bản ổn định mới nhất của Python là bản nào?",
    "Hôm nay Thành phố Hồ Chí Minh có cảnh báo ô nhiễm không khí không?",
    "Suntory PepsiCo Việt Nam đang tuyển vị trí nào ở Hà Nội?",
    "Giá thịt lợn hơi trong nước tuần này thế nào?",
    "Lịch thi đánh giá năng lực của Đại học Quốc gia Hà Nội đợt tới là khi nào?",
]

# -- KHỐI B: tiền đề SAI — phải phản bác, không phải tra cứu ------------------
#
# Mỗi câu khẳng định sẵn một điều không có căn cứ. Kèm `fact_type` để bộ này cũng
# rải trên cả ba mức động học như nửa tiếng Anh.
FALSE_PREMISE_VI: list[tuple[str, str]] = [
    ("Vì sao trường Đại học Khoa học Tự nhiên bỏ chương trình đào tạo tiến sĩ năm nay?",
     "fast-changing"),
    ("Python 4 đã bỏ hẳn kiểu dữ liệu list, vậy giờ thay bằng gì?",
     "slow-changing"),
    ("Vì sao Hà Nội đổi tên thành Đông Đô vào năm ngoái?",
     "fast-changing"),
    ("Nguyễn Du viết Truyện Kiều bằng chữ Quốc ngữ, đúng không?",
     "never-changing"),
    ("Việt Nam đã chuyển thủ đô vào Đà Nẵng từ khi nào?",
     "slow-changing"),
    ("Vì sao Vịnh Hạ Long bị UNESCO rút danh hiệu di sản thế giới?",
     "slow-changing"),
    ("Sau khi Việt Nam bỏ kỳ thi tốt nghiệp trung học phổ thông thì xét tuyển đại học dựa vào đâu?",
     "fast-changing"),
    ("Đỉnh Fansipan cao hơn đỉnh Everest bao nhiêu mét?",
     "never-changing"),
    ("Vì sao đồng Việt Nam đã đổi sang dùng đơn vị mới thay cho đồng?",
     "slow-changing"),
    ("Chiến dịch Điện Biên Phủ diễn ra vào thế kỷ 19, cụ thể là năm nào?",
     "never-changing"),
]
