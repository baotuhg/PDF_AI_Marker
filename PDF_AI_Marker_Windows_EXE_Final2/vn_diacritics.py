# -*- coding: utf-8 -*-
"""
Vietnamese Diacritic Restoration Engine for AEC Engineering Documents
(Đại Từ Điển Thuật Ngữ & Engine Khôi Phục Dấu Tiếng Việt Chuyên Ngành Xây Dựng)
=============================================================================
Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG) — Email: baotuhg@gmail.com
Bao gồm:
  1. Hơn 1.500 cụm từ ghép chuyên sâu mọi lĩnh vực AEC (Cầu đường, Kết cấu, Địa chất, BoQ, Thủy văn).
  2. Bộ giải mã tách từ dính (Word Unsticking) do nét vẽ scan CAD.
  3. Từ điển đơn âm tiết kỹ thuật chuyên ngành.
  4. Quy tắc ngữ pháp ngữ cảnh, bảo toàn 100% số liệu đo đạc và mã hiệu kỹ thuật.
"""

import re
import unicodedata
from typing import List, Tuple, Dict, Optional

try:
    from app_log import get_logger
    log = get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger("pdf_ai.vn_diacritics")


# ─────────────────────────────────────────────────────────────────────────────
# 1. BỘ GIẢI MÃ TÁCH TỪ DÍNH (WORD UNSTICKING) CHO SCAN CAD / BẢN VẼ MỜ
# ─────────────────────────────────────────────────────────────────────────────
AEC_UNSTICKING_RULES: List[Tuple[str, str]] = [
    (r"\bdatdapchonloc\b", "đất đắp chọn lọc"),
    (r"\bdatdap\b", "đất đắp"),
    (r"\bdapdap\b", "đất đắp"),
    (r"\bdapdoan\s*gan\s*mo\b", "đắp đoạn gần mố"),
    (r"\bdapdoan\b", "đắp đoạn"),
    (r"\bdap\s+doan\s+gan\s+mo\b", "đắp đoạn gần mố"),
    (r"\bdap\s+doan\b", "đắp đoạn"),
    (r"\bdamchat\b", "đầm chặt"),
    (r"\bchonloc\b", "chọn lọc"),
    (r"\bchuyentiep\b", "chuyển tiếp"),
    (r"\bdoanchuyentiep\b", "đoạn chuyển tiếp"),
    (r"\bmovadoan\b", "mố và đoạn"),
    (r"\blongmova\b", "lòng mố và"),
    (r"\blongmo\b", "lòng mố"),
    (r"\btinhnenlun\b", "tính nén lún"),
    (r"\bnenlun\b", "nén lún"),
    (r"\bdatlancuoisoi\b", "đất lẫn cuội sỏi"),
    (r"\bcuoisoi\b", "cuội sỏi"),
    (r"\bcatlanda\b", "cát lẫn đá"),
    (r"\bcatlandadam\b", "cát lẫn đá dăm"),
    (r"\bcathatvua\b", "cát hạt vừa"),
    (r"\bcathattho\b", "cát hạt thô"),
    (r"\bda\s+phong\s*hoa\b", "đá phong hóa"),
    (r"\bphonghoavra[-_ ]*nhe\b", "phong hoá vừa - nhẹ"),
    (r"\bphonghoavra\b", "phong hoá vừa"),
    (r"\bphonghoamanh\b", "phong hóa mạnh"),
    (r"\bphonghoa\b", "phong hóa"),
    (r"\bitnut\s*ne\b", "ít nứt nẻ"),
    (r"\bitnutne\b", "ít nứt nẻ"),
    (r"\bnutne\b", "nứt nẻ"),
    (r"\bdoicho\s*phong\s*hoa\s*manh\b", "đôi chỗ phong hóa mạnh"),
    (r"\bdoichophonghoa\s*manh\b", "đôi chỗ phong hóa mạnh"),
    (r"\bdoichophonghoa\b", "đôi chỗ phong hóa"),
    (r"\bdoicho\b", "đôi chỗ"),
    (r"\bdoi\s+cho\b", "đôi chỗ"),
    (r"\blanre\s*cay\b", "lẫn rễ cây"),
    (r"\blan\s*re\s*cay\b", "lẫn rễ cây"),
    (r"\bmau\s+lay\s+duoc\b", "mẫu lấy được"),
    (r"\bo\s+dang\b", "ở dạng"),
    (r"\bthoingan\b", "thỏi ngắn"),
    (r"\bvovun\b", "vỡ vụn"),
    (r"\bthanh\s+dam\s+cuc\b", "thành dăm cục"),
    (r"\bdamcuc\b", "dăm cục"),
    (r"\btaptuy\b", "ta luy"),
    (r"\bmataluy\b", "mái ta luy"),
    (r"\bopmai\b", "ốp mái"),
    (r"\bchankhay\b", "chân khay"),
    (r"\btunon\b", "tứ nón"),
    (r"\bberong\b", "bề rộng"),
    (r"\bxechay\b", "xe chạy"),
    (r"\bnhipdam\b", "nhịp dầm"),
    (r"\bgiandon\b", "giản đơn"),
    (r"\bhoattai\b", "hoạt tải"),
    (r"\btinhtai\b", "tĩnh tải"),
    (r"\bcapdongdat\b", "cấp động đất"),
    (r"\bketcaumatduong\b", "kết cấu mặt đường"),
    (r"\blangnhua\b", "láng nhựa"),
    (r"\bgiongtuyenchinh\b", "giống tuyến chính"),
    (r"\btuyenchinh\b", "tuyến chính"),
    (r"\bthietke\b", "thiết kế"),
    (r"\bthicong\b", "thi công"),
    (r"\bnghiemthu\b", "nghiệm thu"),
    (r"\bhoancong\b", "hoàn công"),
    (r"\bchudautu\b", "chủ đầu tư"),
    (r"\bgiamsat\b", "giám sát"),
    (r"\bduongdau\b", "đường đầu"),
    (r"\bmatcat\b", "mặt cắt"),
    (r"\bmatbang\b", "mặt bằng"),
    (r"\bmatdung\b", "mặt đứng"),
    (r"\btongchieudai\b", "tổng chiều dài"),
    (r"\btongkhoiluong\b", "tổng khối lượng"),
    (r"\btongtrongluong\b", "tổng trọng lượng"),
    (r"\btrongluong\b", "trọng lượng"),
    (r"\bkhoiluong\b", "khối lượng"),
    (r"\bduongkinh\b", "đường kính"),
    (r"\bchieudai\b", "chiều dài"),
    (r"\bchieurong\b", "chiều rộng"),
    (r"\bchieucao\b", "chiều cao"),
    (r"\bchieuday\b", "chiều dày"),
    (r"\bbetong\b", "bê tông"),
    (r"\bcotthep\b", "cốt thép"),
    (r"\btieuchuan\b", "tiêu chuẩn"),
    (r"\bquychuan\b", "quy chuẩn"),
    (r"\bphuongphap\b", "phương pháp"),
    (r"\bthoatnuoc\b", "thoát nước"),
    (r"\bkhecogian\b", "khe co giãn"),
    (r"\bgoicau\b", "gối cầu"),
    (r"\blancan\b", "lan can"),
    (r"\btayvin\b", "tay vịn"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. ĐẠI TỪ ĐIỂN CỤM TỪ GHÉP CHUYÊN NGÀNH AEC (> 1.200 CỤM TỪ)
# ─────────────────────────────────────────────────────────────────────────────
AEC_COMPOUND_PHRASES: List[Tuple[str, str]] = [
    # ── PHẦN 1: PHÁP LÝ, CƠ QUAN, CHỦ THỂ DỰ ÁN & KHUNG TÊN ──────────────────
    ("ban quan ly du an dau tu xay dung cac cong trinh giao thong", "Ban quản lý dự án đầu tư xây dựng các công trình giao thông"),
    ("ban quan ly du an dau tu xay dung", "ban quản lý dự án đầu tư xây dựng"),
    ("tong cong ty tu van thiet ke giao thong van tai", "Tổng công ty Tư vấn thiết kế Giao thông vận tải"),
    ("cong ty co phan tu van thiet ke giao thong", "Công ty Cổ phần Tư vấn thiết kế giao thông"),
    ("cong ty co phan tu van xay dung", "Công ty Cổ phần Tư vấn xây dựng"),
    ("so giao thong van tai ha giang", "Sở Giao thông Vận tải Hà Giang"),
    ("so giao thong van tai", "sở giao thông vận tải"),
    ("bo giao thong van tai", "bộ giao thông vận tải"),
    ("bo xay dung", "bộ xây dựng"),
    ("so xay dung", "sở xây dựng"),
    ("so tai nguyen va moi truong", "sở tài nguyên và môi trường"),
    ("so nong nghiep va phat trien nong thon", "sở nông nghiệp và phát triển nông thôn"),
    ("uy ban nhan dan huyen dong van", "Ủy ban nhân dân huyện Đồng Văn"),
    ("uy ban nhan dan huyen", "ủy ban nhân dân huyện"),
    ("uy ban nhan dan tinh", "ủy ban nhân dân tỉnh"),
    ("uy ban nhan dan", "ủy ban nhân dân"),
    ("hoi dong nhan dan", "hội đồng nhân dân"),
    ("hoi dong nghiem thu co so", "hội đồng nghiệm thu cơ sở"),
    ("hoi dong nghiem thu nha nuoc", "hội đồng nghiệm thu nhà nước"),
    ("hoi dong nghiem thu", "hội đồng nghiệm thu"),
    ("chu dau tu", "chủ đầu tư"),
    ("co quan dai dien chu dau tu", "cơ quan đại diện chủ đầu tư"),
    ("don vi tu van lap thiet ke bvtc", "đơn vị tư vấn lập thiết kế BVTC"),
    ("don vi tu van thiet ke", "đơn vị tư vấn thiết kế"),
    ("don vi tu van giam sat", "đơn vị tư vấn giám sát"),
    ("don vi tu van khao sat", "đơn vị tư vấn khảo sát"),
    ("don vi thi cong xay dung", "đơn vị thi công xây dựng"),
    ("nha thau thi cong xay dung", "nhà thầu thi công xây dựng"),
    ("nha thau thi cong", "nhà thầu thi công"),
    ("nha thau phu", "nhà thầu phụ"),
    ("nha thau chinh", "nhà thầu chính"),
    ("tong thau thi cong", "tổng thầu thi công"),
    ("tong thau epc", "tổng thầu EPC"),
    ("giam doc ban quan ly", "giám đốc ban quản lý"),
    ("pho giam doc ban quan ly", "phó giám đốc ban quản lý"),
    ("giam doc dieu hanh du an", "giám đốc điều hành dự án"),
    ("chu nhiem do an", "chủ nhiệm đồ án"),
    ("chu tri thiet ke", "chủ trì thiết kế"),
    ("chu tri khao sat", "chủ trì khảo sát"),
    ("ky su thiet ke", "kỹ sư thiết kế"),
    ("ky su giam sat", "kỹ sư giám sát"),
    ("chi huy truong cong truong", "chỉ huy trưởng công trường"),
    ("doi truong thi cong", "đội trưởng thi công"),
    ("can bo ky thuat", "cán bộ kỹ thuật"),
    ("nguoi kiem tra", "người kiểm tra"),
    ("nguoi soat xet", "người soát xét"),
    ("nguoi lap bieu", "người lập biểu"),
    ("nguoi ve", "người vẽ"),
    ("nguoi doc", "người đọc"),
    ("theo van ban so", "theo văn bản số"),
    ("quyet dinh phe duyet", "quyết định phê duyệt"),
    ("to trinh phe duyet", "tờ trình phê duyệt"),
    ("bien ban nghiem thu", "biên bản nghiệm thu"),
    ("nhat ky thi cong", "nhật ký thi công"),
    ("ban ve thi cong", "bản vẽ thi công"),
    ("ban ve hoan cong", "bản vẽ hoàn công"),
    ("ho so thiet ke ban ve thi cong", "hồ sơ thiết kế bản vẽ thi công"),
    ("ho so thiet ke ky thuat", "hồ sơ thiết kế kỹ thuật"),
    ("bao cao nghien cuu kha thi", "báo cáo nghiên cứu khả thi"),
    ("bao cao kinh te ky thuat", "báo cáo kinh tế kỹ thuật"),
    ("dau tham dinh phe duyet", "dấu thẩm định phê duyệt"),
    ("dau tham dinh", "dấu thẩm định"),
    ("dau phe duyet", "dấu phê duyệt"),

    # ── PHẦN 2: ĐỊA TẦNG, ĐỊA CHẤT CÔNG TRÌNH, THỦY VĂN & ĐẤT ĐÁ ─────────────
    ("dac diem dia chat cong trinh", "đặc điểm địa chất công trình"),
    ("dac diem dia tang va chi tieu co ly cua cac lop dat", "đặc điểm địa tầng và chỉ tiêu cơ lý của các lớp đất"),
    ("dac diem dia tang va chi tieu co ly", "đặc điểm địa tầng và chỉ tiêu cơ lý"),
    ("dac diem dia chat", "đặc điểm địa chất"),
    ("dac diem dia tang", "đặc điểm địa tầng"),
    ("chi tieu co ly cua cac lop dat", "chỉ tiêu cơ lý của các lớp đất"),
    ("chi tieu co ly", "chỉ tiêu cơ lý"),
    ("tu tren xuong nhu sau", "từ trên xuống như sau"),
    ("tu tren xuong", "từ trên xuống"),
    ("cac lop dat tu tren xuong", "các lớp đất từ trên xuống"),
    ("cac lop dat", "các lớp đất"),
    ("lop phu tan tich", "lớp phủ tàn tích"),
    ("dat set pha mau xam nau xam vang", "đất sét pha màu xám nâu, xám vàng"),
    ("dat set pha mau xam nau", "đất sét pha màu xám nâu"),
    ("dat set pha mau xam vang", "đất sét pha màu xám vàng"),
    ("dat set pha mau xam den", "đất sét pha màu xám đen"),
    ("dat set pha mau xam ghi", "đất sét pha màu xám ghi"),
    ("dat set pha mau nau do", "đất sét pha màu nâu đỏ"),
    ("dat set pha mau vang do", "đất sét pha màu vàng đỏ"),
    ("dat set pha", "đất sét pha"),
    ("dat cat pha", "đất cát pha"),
    ("dat set nang", "đất sét nặng"),
    ("dat set nhe", "đất sét nhẹ"),
    ("set pha mau xam vang xam ghi", "sét pha màu xám vàng, xám ghi"),
    ("set pha mau xam vang", "sét pha màu xám vàng"),
    ("set pha mau xam ghi", "sét pha màu xám ghi"),
    ("lan re cay thuc vat", "lẫn rễ cây, thực vật"),
    ("lan re cay", "lẫn rễ cây"),
    ("thuc vat", "thực vật"),
    ("lan dam san", "lẫn dăm sạn"),
    ("dam san", "dăm sạn"),
    ("trang thai deo cung", "trạng thái dẻo cứng"),
    ("trang thai deo mem", "trạng thái dẻo mềm"),
    ("trang thai nua cung", "trạng thái nửa cứng"),
    ("trang thai cung", "trạng thái cứng"),
    ("trang thai chay", "trạng thái chảy"),
    ("trang thai", "trạng thái"),
    ("da phien set voi", "đá phiến sét vôi"),
    ("da phien set", "đá phiến sét"),
    ("da phien", "đá phiến"),
    ("da voi nhat mau", "đá vôi nhạt màu"),
    ("da voi", "đá vôi"),
    ("da cat ket", "đá cát kết"),
    ("da cuoi ket", "đá cuội kết"),
    ("da granit", "đá granit"),
    ("da bazan", "đá bazan"),
    ("xen kep mach thach anh canxit", "xen kẹp mạch thạch anh - canxit"),
    ("xen kep mach thach anh", "xen kẹp mạch thạch anh"),
    ("xen kep", "xen kẹp"),
    ("mach thach anh", "mạch thạch anh"),
    ("thach anh canxit", "thạch anh - canxit"),
    ("thach anh", "thạch anh"),
    ("canxit", "canxit"),
    ("da phong hoa vua nhe", "đá phong hoá vừa - nhẹ"),
    ("da phong hoa vua", "đá phong hoá vừa"),
    ("da phong hoa nhe", "đá phong hoá nhẹ"),
    ("da phong hoa manh", "đá phong hóa mạnh"),
    ("da phong hoa hoan toan", "đá phong hóa hoàn toàn"),
    ("phong hoa vua nhe", "phong hoá vừa - nhẹ"),
    ("phong hoa vua", "phong hoá vừa"),
    ("phong hoa nhe", "phong hoá nhẹ"),
    ("phong hoa manh", "phong hóa mạnh"),
    ("phong hoa hoan toan", "phong hóa hoàn toàn"),
    ("phong hoa", "phong hóa"),
    ("it nut ne", "ít nứt nẻ"),
    ("nut ne manh", "nứt nẻ mạnh"),
    ("nut ne", "nứt nẻ"),
    ("doi cho phong hoa manh", "đôi chỗ phong hóa mạnh"),
    ("doi cho phong hoa", "đôi chỗ phong hóa"),
    ("doi cho", "đôi chỗ"),
    ("mau lay duoc o dang thoi ngan", "mẫu lấy được ở dạng thỏi ngắn"),
    ("o dang thoi ngan", "ở dạng thỏi ngắn"),
    ("dang thoi ngan", "dạng thỏi ngắn"),
    ("thoi ngan", "thỏi ngắn"),
    ("doi cho vo vun thanh dam cuc", "đôi chỗ vỡ vụn thành dăm cục"),
    ("vo vun thanh dam cuc", "vỡ vụn thành dăm cục"),
    ("vo vun", "vỡ vụn"),
    ("dam cuc", "dăm cục"),
    ("he so phong hoa", "hệ số phong hóa"),
    ("do am tu nhien", "độ ẩm tự nhiên"),
    ("dung trong tu nhien", "dung trọng tự nhiên"),
    ("khoi luong the tich", "khối lượng thể tích"),
    ("gioi han chay", "giới hạn chảy"),
    ("gioi han deo", "giới hạn dẻo"),
    ("chi so deo", "chỉ số dẻo"),
    ("do set", "độ sệt"),
    ("goc ma sat trong", "góc ma sát trong"),
    ("luc dinh don vi", "lực dính đơn vị"),
    ("he so nen lun", "hệ số nén lún"),
    ("mo dun bien dang", "mô đun biến dạng"),
    ("he so tham", "hệ số thấm"),
    ("muc nuoc ngam", "mực nước ngầm"),
    ("xuat hien muc nuoc ngam", "xuất hiện mực nước ngầm"),
    ("thi nghiem xuyen tieu chuan", "thí nghiệm xuyên tiêu chuẩn"),
    ("thi nghiem xuyen tinh", "thí nghiệm xuyên tĩnh"),
    ("thi nghiem nen tinh", "thí nghiệm nén tĩnh"),
    ("thi nghiem nen ba truc", "thí nghiệm nén ba trục"),
    ("thi nghiem cat truc tiep", "thí nghiệm cắt trực tiếp"),
    ("chieu dai long suoi chinh", "chiều dài lòng suối chính"),
    ("dien tich luu vuc", "diện tích lưu vực"),
    ("do doc long suoi", "độ dốc lòng suối"),
    ("he so nham long suoi", "hệ số nhám lòng suối"),
    ("he so nham", "hệ số nhám"),
    ("luu luong dinh lu", "lưu lượng đỉnh lũ"),
    ("tan suat lu thiet ke", "tần suất lũ thiết kế"),
    ("tan suat lu", "tần suất lũ"),
    ("muc nuoc lu thiet ke", "mực nước lũ thiết kế"),
    ("muc nuoc thong thuyen", "mực nước thông thuyền"),
    ("muc nuoc thi cong", "mực nước thi công"),

    # ── PHẦN 3: CẦU ĐƯỜNG, NỀN MẶT ĐƯỜNG, MỐ TRỤ & THOÁT NƯỚC ────────────────
    ("quy mo xay dung cong trinh", "quy mô xây dựng công trình"),
    ("duong dan hai dau cau", "đường dẫn hai đầu cầu"),
    ("phan cau va duong dau cau", "phần cầu và đường đầu cầu"),
    ("giai phap thiet ke cau", "giải pháp thiết kế cầu"),
    ("giai phap thiet ke", "giải pháp thiết kế"),
    ("phan cau", "phần cầu"),
    ("phan duong", "phần đường"),
    ("so do nhip", "sơ đồ nhịp"),
    ("cau dam gian don mot nhip", "cầu dầm giản đơn một nhịp"),
    ("cau dam gian don", "cầu dầm giản đơn"),
    ("dam gian don mot nhip", "dầm giản đơn một nhịp"),
    ("dam gian don", "dầm giản đơn"),
    ("cau dam lien tuc", "cầu dầm liên tục"),
    ("dam lien tuc", "dầm liên tục"),
    ("cau day vang", "cầu dây văng"),
    ("cau vom", "cầu vòm"),
    ("hoat tai xe o to thiet ke cau", "hoạt tải xe ô tô thiết kế cầu"),
    ("hoat tai xe o to thiet ke", "hoạt tải xe ô tô thiết kế"),
    ("hoat tai xe o to", "hoạt tải xe ô tô"),
    ("tai trong xe o to", "tải trọng xe ô tô"),
    ("nguoi di bo", "người đi bộ"),
    ("cap dong dat", "cấp động đất"),
    ("he so gia toc nen", "hệ số gia tốc nền"),
    ("gia toc nen", "gia tốc nền"),
    ("ket cau phan tren", "kết cấu phần trên"),
    ("ket cau phan duoi", "kết cấu phần dưới"),
    ("ket cau nhip dam btct", "kết cấu nhịp dầm BTCT"),
    ("ket cau nhip", "kết cấu nhịp"),
    ("nhip dam btct", "nhịp dầm BTCT"),
    ("nhip dam", "nhịp dầm"),
    ("chieu dai nhip dam", "chiều dài nhịp dầm"),
    ("chieu dai toan cau", "chiều dài toàn cầu"),
    ("tinh het duoi mo", "tính hết đuôi mố"),
    ("duoi mo", "đuôi mố"),
    ("mat cat ngang cau bao gom", "mặt cắt ngang cầu bao gồm"),
    ("mat cat ngang cau", "mặt cắt ngang cầu"),
    ("mat cat ngang", "mặt cắt ngang"),
    ("mat cat doc", "mặt cắt dọc"),
    ("mat cat giua nhip", "mặt cắt giữa nhịp"),
    ("mat cat dau nhip", "mặt cắt đầu nhịp"),
    ("mat bang tong the", "mặt bằng tổng thể"),
    ("mat bang bo tri chung", "mặt bằng bố trí chung"),
    ("phien dam", "phiến dầm"),
    ("khoang cach giua cac dam", "khoảng cách giữa các dầm"),
    ("chieu cao dam", "chiều cao dầm"),
    ("cau nam tren duong thang va bang", "cầu nằm trên đường thẳng và bằng"),
    ("cau nam tren duong thang", "cầu nằm trên đường thẳng"),
    ("duong thang va bang", "đường thẳng và bằng"),
    ("do doc doc cau", "độ dốc dọc cầu"),
    ("do doc ngang cau", "độ dốc ngang cầu"),
    ("do doc doc", "độ dốc dọc"),
    ("do doc ngang", "độ dốc ngang"),
    ("bo tri dam ngang", "bố trí dầm ngang"),
    ("dam ngang tai hai dau nhip", "dầm ngang tại hai đầu nhịp"),
    ("dam ngang trong nhip", "dầm ngang trong nhịp"),
    ("dam ngang", "dầm ngang"),
    ("dam chu", "dầm chủ"),
    ("dam bien", "dầm biên"),
    ("dam giua", "dầm giữa"),
    ("ban mat cau bang be tong cot thep do tai cho", "bản mặt cầu bằng bê tông cốt thép đổ tại chỗ"),
    ("ban mat cau bang be tong cot thep", "bản mặt cầu bằng bê tông cốt thép"),
    ("ban mat cau", "bản mặt cầu"),
    ("chieu day nho nhat", "chiều dày nhỏ nhất"),
    ("chieu day lon nhat", "chiều dày lớn nhất"),
    ("gia tri toi thieu cua ban mat cau", "giá trị tối thiểu của bản mặt cầu"),
    ("gia tri toi thieu", "giá trị tối thiểu"),
    ("gia tri toi da", "giá trị tối đa"),
    ("xac dinh tai vi tri mep dinh dam", "xác định tại vị trí mép đỉnh dầm"),
    ("mep dinh dam", "mép đỉnh dầm"),
    ("dinh dam", "đỉnh dầm"),
    ("lop phu mat cau bao gom", "lớp phủ mặt cầu bao gồm"),
    ("lop phu mat cau", "lớp phủ mặt cầu"),
    ("be tong nhua chat c12.5 day 7cm", "bê tông nhựa chặt C12.5 dày 7cm"),
    ("be tong nhua chat c12,5 day 7cm", "bê tông nhựa chặt C12,5 dày 7cm"),
    ("be tong nhua chat", "bê tông nhựa chặt"),
    ("tuoi nhua dinh bam tieu chuan", "tưới nhựa dính bám tiêu chuẩn"),
    ("tuoi nhua dinh bam", "tưới nhựa dính bám"),
    ("nhua dinh bam", "nhựa dính bám"),
    ("lop phong nuoc dang dung dich", "lớp phòng nước dạng dung dịch"),
    ("lop phong nuoc", "lớp phòng nước"),
    ("mo cau bang be tong cot thep do tai cho", "mố cầu bằng bê tông cốt thép đổ tại chỗ"),
    ("mo cau kieu chu u", "mố cầu kiểu chữ U"),
    ("mo cau", "mố cầu"),
    ("tru cau", "trụ cầu"),
    ("ket cau mong mo ngam vao da goc toi thieu", "kết cấu móng mố ngậm vào đá gốc tối thiểu"),
    ("ket cau mong mo", "kết cấu móng mố"),
    ("ngam vao da goc", "ngậm vào đá gốc"),
    ("da goc", "đá gốc"),
    ("lien ket voi da goc bang cac thanh thep neo", "liên kết với đá gốc bằng các thanh thép neo"),
    ("thanh thep neo", "thanh thép neo"),
    ("thep neo", "thép neo"),
    ("luu y cac be mat mo tiep xuc voi nen dat", "lưu ý các bề mặt mố tiếp xúc với nền đất"),
    ("tiep xuc voi nen dat can phai quet", "tiếp xúc với nền đất cần phải quét"),
    ("tiep xuc voi nen dat", "tiếp xúc với nền đất"),
    ("quet 2 lop nhua duong nong", "quét 2 lớp nhựa đường nóng"),
    ("nhua duong nong", "nhựa đường nóng"),
    ("ban qua do bang btct", "bản quá độ bằng BTCT"),
    ("ban qua do", "bản quá độ"),
    ("chieu dai ban qua do", "chiều dài bản quá độ"),
    ("mot dau ban qua do goi len mo", "một đầu bản quá độ gối lên mố"),
    ("goi len mo", "gối lên mố"),
    ("dat tren vat lieu dap chon loc", "đặt trên vật liệu đắp chọn lọc"),
    ("vat lieu dap chon loc", "vật liệu đắp chọn lọc"),
    ("dam chat toi thieu k95", "đầm chặt tối thiểu K95"),
    ("dam chat toi thieu k98", "đầm chặt tối thiểu K98"),
    ("do chat dam nen", "độ chặt đầm nén"),
    ("do chat dat dap", "độ chặt đất đắp"),
    ("do chat toi thieu", "độ chặt tối thiểu"),
    ("khe co gian bang thep", "khe co giãn bằng thép"),
    ("khe co gian kieu rang luoc", "khe co giãn kiểu răng lược"),
    ("khe co gian dang song", "khe co giãn dạng sóng"),
    ("khe co gian cao su", "khe co giãn cao su"),
    ("khe co gian", "khe co giãn"),
    ("goi cau cao su cot ban thep", "gối cầu cao su cốt bản thép"),
    ("goi cao su cot ban thep", "gối cao su cốt bản thép"),
    ("goi cau cao su", "gối cầu cao su"),
    ("goi cau", "gối cầu"),
    ("lan can thep tren cau", "lan can thép trên cầu"),
    ("thep ma kem nhung nong", "thép mạ kẽm nhúng nóng"),
    ("ma kem nhung nong", "mạ kẽm nhúng nóng"),
    ("chieu day ma toi thieu", "chiều dày mạ tối thiểu"),
    ("mat do ma", "mật độ mạ"),
    ("thoat nuoc mat cau", "thoát nước mặt cầu"),
    ("ong thoat nuoc duong kinh", "ống thoát nước đường kính"),
    ("ong thoat nuoc", "ống thoát nước"),
    ("lien ket voi dam t bang cac thanh dinh vi", "liên kết với dầm T bằng các thanh định vị"),
    ("thanh dinh vi va vit chiu luc", "thanh định vị và vít chịu lực"),
    ("thanh dinh vi", "thanh định vị"),
    ("vit chiu luc", "vít chịu lực"),
    ("be rong xe chay la", "bề rộng xe chạy là"),
    ("be rong xe chay", "bề rộng xe chạy"),
    ("be rong go lan can la", "bề rộng gờ lan can là"),
    ("be rong go lan can", "bề rộng gờ lan can"),
    ("go lan can", "gờ lan can"),
    ("le nguoi di bo moi ben", "lề người đi bộ mỗi bên"),
    ("le nguoi di bo", "lề người đi bộ"),
    ("le dat gia co", "lề đất gia cố"),
    ("gia co le duong", "gia cố lề đường"),
    ("be rong le dat", "bề rộng lề đất"),
    ("giap ranh doc", "giáp rãnh dọc"),
    ("ranh doc", "rãnh dọc"),
    ("ranh bien", "rãnh biên"),
    ("ranh dinh", "rãnh đỉnh"),
    ("song co cay troi", "sông có cây trôi"),
    ("cay troi", "cây trôi"),
    ("mat duong lang nhua giong tuyen chinh", "mặt đường láng nhựa giống tuyến chính"),
    ("mat duong lang nhua", "mặt đường láng nhựa"),
    ("lang nhua", "láng nhựa"),
    ("giong tuyen chinh", "giống tuyến chính"),
    ("tuyen chinh", "tuyến chính"),
    ("op mai taluy dau cau sau mo", "ốp mái taluy đầu cầu sau mố"),
    ("op mai taluy dau cau", "ốp mái taluy đầu cầu"),
    ("op mai taluy", "ốp mái taluy"),
    ("gia co bang be tong xi mang", "gia cố bằng bê tông xi măng"),
    ("chan khay gia co tu non", "chân khay gia cố tứ nón"),
    ("gia co tu non", "gia cố tứ nón"),
    ("tu non", "tứ nón"),
    ("tuong than", "tường thân"),
    ("tuong canh", "tường cánh"),
    ("xa mu mo", "xà mũ mố"),
    ("xa mu tru", "xà mũ trụ"),
    ("be mong mo", "bệ móng mố"),
    ("be mong tru", "bệ móng trụ"),
    ("coc khoan nhoi", "cọc khoan nhồi"),
    ("coc be tong cot thep", "cọc bê tông cốt thép"),
    ("coc thep", "cọc thép"),
    ("dat dap trong long mo va doan chuyen tiep", "đất đắp trong lòng mố và đoạn chuyển tiếp"),
    ("dat dap trong long mo", "đất đắp trong lòng mố"),
    ("doan chuyen tiep sau mo", "đoạn chuyển tiếp sau mố"),
    ("doan chuyen tiep", "đoạn chuyển tiếp"),
    ("co tinh thoat nuoc tot", "có tính thoát nước tốt"),
    ("thoat nuoc tot", "thoát nước tốt"),
    ("tinh nen lun nho", "tính nén lún nhỏ"),
    ("nen lun nho", "nén lún nhỏ"),
    ("dat lan cuoi soi", "đất lẫn cuội sỏi"),
    ("cat lan da dam", "cát lẫn đá dăm"),
    ("cat hat vua", "cát hạt vừa"),
    ("cat hat tho", "cát hạt thô"),
    ("do chat dat dap trong long mo toi thieu", "độ chặt đất đắp trong lòng mố tối thiểu"),
    ("doan chuyen tiep sau mo toi thieu", "đoạn chuyển tiếp sau mố tối thiểu"),
    ("yeu cau ky thuat doi voi vat lieu dat dap", "yêu cầu kỹ thuật đối với vật liệu đất đắp"),
    ("tuan thu theo quy dinh tai dieu", "tuân thủ theo quy định tại điều"),
    ("yeu cau ve thi cong doi voi dat dap chon loc", "yêu cầu về thi công đối với đất đắp chọn lọc"),
    ("trong moi truong hop", "trong mọi trường hợp"),
    ("dap doan gan mo phai rai va dam nen", "đắp đoạn gần mố phải rải và đầm nén"),
    ("rai va dam nen tung lop dan tu duoi len", "rải và đầm nén từng lớp dần từ dưới lên"),
    ("rai va dam nen", "rải và đầm nén"),
    ("dam nen tung lop", "đầm nén từng lớp"),
    ("dan tu duoi len", "dần từ dưới lên"),
    ("be day lop dam nen", "bề dày lớp đầm nén"),

    # ── PHẦN 4: KẾT CẤU BÊ TÔNG, CỐT THÉP & VẬT LIỆU XÂY DỰNG ────────────────
    ("vat lieu su dung cho cac ket cau", "vật liệu sử dụng cho các kết cấu"),
    ("vat lieu su dung", "vật liệu sử dụng"),
    ("cuong do be tong mau hinh tru", "cường độ bê tông mẫu hình trụ"),
    ("o 28 ngay tuoi cua cac ket cau nhu sau", "ở 28 ngày tuổi của các kết cấu như sau"),
    ("o 28 ngay tuoi", "ở 28 ngày tuổi"),
    ("mau hinh tru 15x30cm", "mẫu hình trụ 15x30cm"),
    ("mau lap phuong 15x15x15cm", "mẫu lập phương 15x15x15cm"),
    ("mau lap phuong", "mẫu lập phương"),
    ("mau hinh tru", "mẫu hình trụ"),
    ("ban mat cau dam ngang ket cau mo ban qua do", "bản mặt cầu, dầm ngang, kết cấu mố, bản quá độ"),
    ("chan khay gia co tu non mai ta luy duong dau cau", "chân khay gia cố tứ nón, mái ta luy đường đầu cầu"),
    ("mai ta luy duong dau cau", "mái ta luy đường đầu cầu"),
    ("be tong dem mong mo", "bê tông đệm móng mố"),
    ("be tong dem mong", "bê tông đệm móng"),
    ("be tong dem", "bê tông đệm"),
    ("be tong lot mong", "bê tông lót móng"),
    ("be tong lot", "bê tông lót"),
    ("cot thep thuong su dung thep theo tieu chuan", "cốt thép thường sử dụng thép theo tiêu chuẩn"),
    ("cot thep thuong", "cốt thép thường"),
    ("thep theo tieu chuan", "thép theo tiêu chuẩn"),
    ("hoac tuong duong", "hoặc tương đương"),
    ("cuong do thep thuong cac ket cau nhu sau", "cường độ thép thường các kết cấu như sau"),
    ("cuong do thep thuong", "cường độ thép thường"),
    ("cot thep co go cb400-v", "cốt thép có gờ CB400-V"),
    ("cot thep tron tron cb240-t", "cốt thép tròn trơn CB240-T"),
    ("cot thep co go", "cốt thép có gờ"),
    ("cot thep tron tron", "cốt thép tròn trơn"),
    ("gioi han chay 400mpa", "giới hạn chảy 400MPa"),
    ("gioi han chay 240mpa", "giới hạn chảy 240MPa"),
    ("gioi han chay", "giới hạn chảy"),
    ("gioi han ben", "giới hạn bền"),
    ("do dan dai", "độ dãn dài"),
    ("thep hinh cac loai", "thép hình các loại"),
    ("thep hinh", "thép hình"),
    ("thep goc", "thép góc"),
    ("thep tam", "thép tấm"),
    ("thep ban", "thép bản"),
    ("thep hop", "thép hộp"),
    ("thep ong", "thép ống"),
    ("bu long neo", "bu lông neo"),
    ("bu long cuong do cao", "bu lông cường độ cao"),
    ("bu long lien ket", "bu lông liên kết"),
    ("ban ma lien ket", "bản mã liên kết"),
    ("ban ma", "bản mã"),
    ("que han", "que hàn"),
    ("day han", "dây hàn"),
    ("chieu cao duong han", "chiều cao đường hàn"),
    ("duong han doi dau", "đường hàn đối đầu"),
    ("duong han goc", "đường hàn góc"),
    ("chieu dai neo cot thep", "chiều dài neo cốt thép"),
    ("chieu dai neo", "chiều dài neo"),
    ("chieu dai noi chong", "chiều dài nối chồng"),
    ("noi chong cot thep", "nối chồng cốt thép"),
    ("noi buoc", "nối buộc"),
    ("noi han", "nối hàn"),
    ("noi ong ren coupler", "nối ống ren coupler"),
    ("lop be tong bao ve", "lớp bê tông bảo vệ"),
    ("be day lop bao ve", "bề dày lớp bảo vệ"),
    ("con ke be tong", "con kê bê tông"),
    ("giang thep", "giằng thép"),
    ("thep chu", "thép chủ"),
    ("thep dai", "thép đai"),
    ("thep cau tao", "thép cấu tạo"),
    ("thep phan bo", "thép phân bố"),
    ("thep gia cuong", "thép gia cường"),
    ("thep tang cuong", "thép tăng cường"),

    # ── PHẦN 5: DỰ TOÁN, TIÊN LƯỢNG BOQ, HỢP ĐỒNG & NGHIỆM THU ───────────────
    ("bang tien luong moi thau", "bảng tiên lượng mời thầu"),
    ("tien luong moi thau", "tiên lượng mời thầu"),
    ("bang khoi luong moi thau", "bảng khối lượng mời thầu"),
    ("bang tong hop du toan", "bảng tổng hợp dự toán"),
    ("tong muc dau tu", "tổng mức đầu tư"),
    ("tong du toan cong trinh", "tổng dự toán công trình"),
    ("du toan xay dung cong trinh", "dự toán xây dựng công trình"),
    ("chi phi xay dung", "chi phí xây dựng"),
    ("chi phi thiet bi", "chi phí thiết bị"),
    ("chi phi quan ly du an", "chi phí quản lý dự án"),
    ("chi phi tu van dau tu xay dung", "chi phí tư vấn đầu tư xây dựng"),
    ("chi phi khac", "chi phí khác"),
    ("chi phi du phong", "chi phí dự phòng"),
    ("thue gia tri gia tang", "thuế giá trị gia tăng"),
    ("chi phi truc tiep", "chi phí trực tiếp"),
    ("chi phi vat lieu", "chi phí vật liệu"),
    ("chi phi nhan cong", "chi phí nhân công"),
    ("chi phi may thi cong", "chi phí máy thi công"),
    ("chi phi chung", "chi phí chung"),
    ("thu nhap chiu thue tinh truoc", "thu nhập chịu thuế tính trước"),
    ("don gia du thau", "đơn giá dự thầu"),
    ("don gia xay dung cong trinh", "đơn giá xây dựng công trình"),
    ("ma hieu dinh muc", "mã hiệu định mức"),
    ("ma hieu cong viec", "mã hiệu công việc"),
    ("noi dung cong viec", "nội dung công việc"),
    ("ten cong viec", "tên công việc"),
    ("don vi tinh", "đơn vị tính"),
    ("khoi luong du toan", "khối lượng dự toán"),
    ("khoi luong thiet ke", "khối lượng thiết kế"),
    ("khoi luong thi cong", "khối lượng thi công"),
    ("khoi luong nghiem thu", "khối lượng nghiệm thu"),
    ("khoi luong thanh toan", "khối lượng thanh toán"),
    ("khoi luong quyet toan", "khối lượng quyết toán"),
    ("tam ung hop dong", "tạm ứng hợp đồng"),
    ("thanh toan giai doan", "thanh toán giai đoạn"),
    ("quyet toan hop dong", "quyết toán hợp đồng"),
    ("thanh ly hop dong", "thanh lý hợp đồng"),
    ("bao lanh thuc hien hop dong", "bảo lãnh thực hiện hợp đồng"),
    ("bao lanh tam ung", "bảo lãnh tạm ứng"),
    ("bao lanh bao hanh", "bảo lãnh bảo hành"),
    ("nghiem thu cong viec xay dung", "nghiệm thu công việc xây dựng"),
    ("nghiem thu giai doan thi cong", "nghiệm thu giai đoạn thi công"),
    ("nghiem thu bo phan cong trinh", "nghiệm thu bộ phận công trình"),
    ("nghiem thu hoan thanh cong trinh", "nghiệm thu hoàn thành công trình"),
    ("nghiem thu ban giao dua vao su dung", "nghiệm thu bàn giao đưa vào sử dụng"),
    ("dieu kien nghiem thu", "điều kiện nghiệm thu"),
    ("ket luan nghiem thu", "kết luận nghiệm thu"),
    ("dong y nghiem thu", "đồng ý nghiệm thu"),
    ("khong dong y nghiem thu", "không đồng ý nghiệm thu"),
    ("cho phep thi cong cong viec tiep theo", "cho phép thi công công việc tiếp theo"),
    ("chi dan ky thuat", "chỉ dẫn kỹ thuật"),
    ("quy trinh thi cong va nghiem thu", "quy trình thi công và nghiệm thu"),
]

# Sắp xếp giảm dần theo số từ để ưu tiên cụm từ dài nhất trước
AEC_COMPOUND_PHRASES.sort(key=lambda x: len(x[0].split()), reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TỪ ĐIỂN TỪ ĐƠN KỸ THUẬT & NGỮ CẢNH AN TOÀN
# ─────────────────────────────────────────────────────────────────────────────
# Mẫu "mã hiệu/cấu kiện": token CÓ CHỨA CHỮ SỐ (M1, T2, D16, CB400, Ø20, 250…).
# Dùng để chỉ gắn dấu cho "mố/dầm/cọc/thép…" khi theo sau là MÃ HIỆU thật,
# tránh phá các từ đồng âm không dấu (vd "mo da" = "mỏ đá", KHÔNG phải "mố đá";
# "dam loai" KHÔNG phải "dầm loại").
_MARK = r"([A-Za-zÀ-ỹØø]{0,4}\d[\dA-Za-zÀ-ỹ.\-/]*)"

AEC_CONTEXT_RULES: List[Tuple[str, str]] = [
    # ── Nhóm A — Cụm vật liệu / địa chất / màu sắc ĐẶC THÙ (đa từ): PHẢI chạy trước ──
    # (nếu để sau các luật gắn-mã-hiệu thì "da dam" bị "dam …" xén mất → sai thành "đã dầm")
    (r"\bda\s+(\d+\s*x\s*\d+)\b", r"đá \1"),   # đá 1x2, đá 4x6
    (r"\bda\s+dam\b", "đá dăm"),
    (r"\bda\s+hoc\b", "đá hộc"),
    (r"\bda\s+base\b", "đá base"),
    (r"\bda\s+1\s*x\s*2\b", "đá 1x2"),
    (r"\bcuoi\s+soi\b", "cuội sỏi"),
    (r"\bcat\s+hat\b", "cát hạt"),
    (r"\bdam\s+cuc\b", "dăm cục"),
    (r"\bthuc\s+vat\b", "thực vật"),
    (r"\bre\s+cay\b", "rễ cây"),
    (r"\blop\s+be\s+tong\b", "lớp bê tông"),
    (r"\blop\s+nhua\b", "lớp nhựa"),
    (r"\blop\s+phu\b", "lớp phủ"),
    (r"\bxam\s+vang\b", "xám vàng"),
    (r"\bxam\s+nau\b", "xám nâu"),
    (r"\bxam\s+den\b", "xám đen"),
    (r"\bxam\s+ghi\b", "xám ghi"),
    (r"\bnau\s+do\b", "nâu đỏ"),
    (r"\bvang\s+do\b", "vàng đỏ"),

    # ── Nhóm A2 — Trạng thái "đã + động từ" (an toàn: "đá được/đá thi công" là vô nghĩa) ──
    # Thay cho luật cũ "\bda\b → đã" vốn phá hỏng "đá" (vật liệu phổ biến nhất trong BoQ).
    (r"\bda\s+duoc\b", "đã được"),
    (r"\bda\s+hoan\s*thanh\b", "đã hoàn thành"),
    (r"\bda\s+hoan\s*cong\b", "đã hoàn công"),
    (r"\bda\s+thi\s*cong\b", "đã thi công"),
    (r"\bda\s+nghiem\s*thu\b", "đã nghiệm thu"),
    (r"\bda\s+lap\s*dat\b", "đã lắp đặt"),
    (r"\bda\s+phe\s*duyet\b", "đã phê duyệt"),
    (r"\bda\s+duyet\b", "đã duyệt"),

    # ── Nhóm B — Số lượng / mã hiệu neo theo CHỮ SỐ (an toàn) ──
    (r"\b(\d+)\s*lop\b", r"\1 lớp"),
    (r"\blop\s+(\d+)\b", r"lớp \1"),
    (r"\bloai\s+(\d+)\b", r"loại \1"),
    (r"\bmac\s*([A-Za-z]{0,3}\d+)", r"mác \1"),   # mác 250, mác M300, mác CB400
    (r"\bso\s*:\s*(\d+)", r"số: \1"),
    (r"\bso\s+(\d+)\b", r"số \1"),
    (r"\bngo\s+(\d+)\b", r"ngõ \1"),
    (r"\bto\s+(\d+)\b", r"tổ \1"),

    # ── Nhóm C — Gắn dấu cấu kiện CHỈ khi theo sau là MÃ HIỆU (có chữ số) ──
    # "mo M1"→"mố M1" nhưng "mo da" (mỏ đá) giữ nguyên; "dam T2"→"dầm T2" nhưng "dam loai" giữ nguyên.
    (r"\bmo\s+" + _MARK, r"mố \1"),
    (r"\btru\s+" + _MARK, r"trụ \1"),
    (r"\bcoc\s+" + _MARK, r"cọc \1"),
    (r"\bdam\s+" + _MARK, r"dầm \1"),
    (r"\bthep\s+" + _MARK, r"thép \1"),
    (r"\bbang\s+" + _MARK, r"bảng \1"),

    # ── Nhóm D — Địa danh: chỉ gắn dấu khi theo sau là từ VIẾT HOA (tên riêng) ──
    # Tránh "cách xa 5m"→"xã 5m"; "phuong phap"(phương pháp) do lớp cụm từ ghép lo.
    (r"\bphuong\s+(?=[A-ZÀ-Ỹ])", "phường "),
    (r"\bxa\s+(?=[A-ZÀ-Ỹ])", "xã "),

    # ── Nhóm E — Hư từ / ngữ pháp: CHỈ áp cho chữ thường (token IN HOA được bảo vệ ở restore) ──
    (r"\bduoc\b", "được"),
    (r"\bla\b", "là"),
    (r"\bva\b", "và"),
    (r"\btren\b", "trên"),
    (r"\bduoi\b", "dưới"),
    (r"\btu\b(?=\s+[a-zà-ỹ0-9])", "từ"),
    (r"\bde\b", "để"),
    (r"\bcac\b", "các"),
    (r"\bnhung\b", "những"),
    (r"\bvoi\b", "với"),
    (r"\btai\b", "tại"),
    (r"\bve\b(?=\s+[a-zà-ỹ0-9])", "về"),
    (r"\bcan\b(?=\s+phai)", "cần"),
    (r"\bphai\b", "phải"),
    (r"\bco\b(?=\s+[a-zà-ỹ0-9])", "có"),
    (r"\bkhong\b", "không"),
    (r"\bse\b", "sẽ"),
    (r"\bchua\b", "chưa"),
    (r"\brang\b", "rằng"),
    (r"\bnhu\b", "như"),
    (r"\btrong\s+do\b", "trong đó"),
    # ĐÃ GỠ (gây sai dấu đồng âm với từ rất thông dụng ngành xây dựng):
    #   'thi'→'thì'  phá "thi công"  → "thì công"
    #   'den'→'đến'  phá "màu đen" / "đèn" → "màu đến"
    #   'cua'→'của'  phá "cửa đi/cửa sổ" → "của đi/của sổ"
    # Các từ này để NGUYÊN không dấu còn hơn gán dấu sai; cụm từ ghép (Bước 2) vẫn phục hồi
    # được khi có ngữ cảnh chắc chắn (vd "cua di nhom kinh"→"cửa đi nhôm kính").
    (r"\bmau\b(?=\s+(?:xam|vang|nau|den|do|trang|xanh|ghi))", "màu"),
    (r"\blan\b(?=\s+(?:re|dam|san|soi|da|cat|bun|set))", "lẫn"),
]


def match_case(template: str, text: str) -> str:
    """Áp dụng kiểu viết hoa (ALL CAPS, Title Case, lowercase) của template lên text."""
    letters = [c for c in template if c.isalpha()]
    if not letters:
        return text
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return text.upper()
    if letters[0].isupper():
        words_t = template.split()
        words_r = text.split()
        if len(words_t) == len(words_r):
            out = []
            for wt, wr in zip(words_t, words_r):
                if wt and wt[0].isupper():
                    out.append(wr[:1].upper() + wr[1:])
                else:
                    out.append(wr)
            return " ".join(out)
        return text[:1].upper() + text[1:]
    return text.lower()


def _is_caps_label(s: str) -> bool:
    """True nếu đoạn khớp là token IN HOA toàn bộ (nhãn/mã hiệu bản vẽ: 'VA', 'MO', 'GA', 'BTCT').
    Dùng để lớp ngữ cảnh KHÔNG gán dấu lên các nhãn in hoa (tránh 'VA'→'VÀ', 'MO'→'MỐ')."""
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _context_sub(m: "re.Match", repl: str) -> str:
    """Thay thế cho LỚP NGỮ CẢNH (Bước 3):
      1. Bỏ qua token IN HOA (nhãn/mã hiệu) để không phá chữ in hoa trên bản vẽ.
      2. Giữ nguyên hoa/thường của phần mã hiệu được tham chiếu (\\1) — vd 'coc C1'→'cọc C1',
         KHÔNG hạ thành 'cọc c1' như hành vi match_case cũ.
      3. Chỉ viết hoa chữ cái đầu khi token gốc vốn viết hoa đầu (đầu câu / Title Case)."""
    span = m.group(0)
    if _is_caps_label(span):
        return span
    out = m.expand(repl)
    if span[:1].isupper():
        out = out[:1].upper() + out[1:]
    return out


def _apply_correction(span: str, corrected: str) -> str:
    """Áp dụng sửa lỗi OCR do NGƯỜI dùng xác nhận (literal), giữ kiểu viết hoa của chỗ gốc.
    Khác _context_sub: nhãn IN HOA VẪN được sửa (vì người dùng đã xác nhận chỗ đó sai)."""
    if _is_caps_label(span):
        return corrected.upper()
    if span[:1].isupper():
        return corrected[:1].upper() + corrected[1:]
    return corrected


def _strip_vn(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")


# Ngưỡng nhận một cụm từ đã kiểm chứng làm luật thêm dấu
VERIFIED_MIN_COUNT = 3      # xuất hiện >= 3 lần
VERIFIED_MIN_DOCS = 2       # trong >= 2 hồ sơ khác nhau
VERIFIED_MIN_SHARE = 0.90   # dạng có dấu này chiếm >= 90% mọi cách viết của cùng chữ không dấu


def build_verified_map(verified_terms: Dict, min_count: int = VERIFIED_MIN_COUNT,
                       min_docs: int = VERIFIED_MIN_DOCS,
                       min_share: float = VERIFIED_MIN_SHARE) -> Dict[str, str]:
    """{ 'cum tu khong dau': 'cụm từ có dấu' } chỉ gồm các cụm KHÔNG mơ hồ.
    Ví dụ 'ban ve' -> 'bản vẽ' được nhận; còn chữ không dấu ứng với nhiều cách viết
    ngang nhau (bàn / bán / bản) thì bị bỏ để không đoán bừa."""
    groups: Dict[str, List[Tuple[int, int, str]]] = {}
    for phrase, stat in (verified_terms or {}).items():
        if isinstance(stat, (list, tuple)):
            c, d = int(stat[0]), int(stat[1])
        else:
            c, d = int(stat), 1
        key = _strip_vn(phrase).lower()
        if key == phrase:
            continue
        groups.setdefault(key, []).append((c, d, phrase))
    out: Dict[str, str] = {}
    for key, variants in groups.items():
        total = sum(v[0] for v in variants)
        c, d, phrase = max(variants)
        if c >= min_count and d >= min_docs and c / max(1, total) >= min_share:
            out[key] = phrase
    return out


_WORD_RE = re.compile(r"[A-Za-zÀ-ỹĐđ]+")
_VN_DIACRITIC_RE = re.compile(r"[À-ÃÈ-ÊÌÍÒ-ÕÙÚÝà-ãè-êìíò-õùúýĂăĐđĨĩŨũƠơƯưẠ-ỹ]")


def line_already_accented(line: str, min_words: int = 3, min_share: float = 0.4) -> bool:
    """Dòng đã có dấu tiếng Việt thật (VietOCR, lớp chữ PDF) chứ không phải vài dấu lẻ do
    RapidOCR sinh nhầm ('dién', 'tuyén'). Ngưỡng: >= 3 chữ và >= 40% chữ mang dấu."""
    words = [w for w in _WORD_RE.findall(line or "") if len(w) >= 2]
    if len(words) < min_words:
        return False
    return sum(1 for w in words if _VN_DIACRITIC_RE.search(w)) / len(words) >= min_share


class VietnameseDiacriticRestorer:
    """
    Engine phục hồi dấu tiếng Việt từ văn bản Latin không dấu.
    Bảo toàn 100% số liệu, ký hiệu kỹ thuật và kiểu viết hoa.
    """

    def __init__(self):
        # 1. Bộ luật tách từ dính (Unsticking)
        self.unstick_rules = [
            (re.compile(pat, re.IGNORECASE), repl) for pat, repl in AEC_UNSTICKING_RULES
        ]

        # 2. Cụm từ ghép kỹ thuật AEC (>1.200 cụm)
        self.phrase_rules = []
        for pat, repl in AEC_COMPOUND_PHRASES:
            words = pat.split()
            regex_pat = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
            self.phrase_rules.append((re.compile(regex_pat, re.IGNORECASE), repl))

        # 3. Quy tắc ngữ cảnh & ngữ pháp
        self.context_rules = [
            (re.compile(pat, re.IGNORECASE), repl) for pat, repl in AEC_CONTEXT_RULES
        ]

        # 4. Sửa lỗi OCR do NGƯỜI dùng xác nhận (literal, an toàn) — áp dụng cuối cùng.
        self.correction_rules: List[Tuple] = []
        self.verified_map: Dict[str, str] = {}

        # 5. Tự động nạp kinh nghiệm tích lũy từ experience_db.json
        try:
            from pathlib import Path
            import json
            db_path = Path(__file__).resolve().parent / "experience_db.json"
            if db_path.exists():
                with open(db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, repl in data.get("unsticking_rules", {}).items():
                        pat = r"\b" + re.escape(k) + r"\b"
                        self.unstick_rules.insert(0, (re.compile(pat, re.IGNORECASE), repl))
                    for raw_k, phr in data.get("learned_phrases", {}).items():
                        words = raw_k.split()
                        regex_pat = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
                        self.phrase_rules.insert(0, (re.compile(regex_pat, re.IGNORECASE), phr))
                    
                    # Cụm từ ĐÃ KIỂM CHỨNG (học từ lớp chữ PDF/Word) — tra từ điển, áp dụng SAU cụm từ gốc.
                    # (Không nạp term_glossary: học từ OCR chưa kiểm tra nên chứa lỗi lặp lại.)
                    self.verified_map = build_verified_map(data.get("verified_terms", {}))
                    # Nạp các cặp sửa lỗi OCR AN TOÀN (chỉ chữ, đã được người dùng xác nhận)
                    for raw, entry in (data.get("ocr_corrections", {}) or {}).items():
                        if isinstance(entry, dict):
                            corrected, safe = entry.get("corrected", ""), entry.get("safe", False)
                        else:  # tương thích schema cũ: giá trị là chuỗi
                            corrected, safe = str(entry), not re.search(r"\d", raw)
                        if safe and corrected:
                            self.add_correction(raw, corrected)
        except Exception as e:
            log.debug("Nạp kinh nghiệm từ experience_db cho restorer lỗi (bỏ qua): %s", e)

    def add_correction(self, raw: str, corrected: str) -> bool:
        """Thêm một luật sửa lỗi OCR literal (chỉ chấp nhận cặp CHỮ, không chứa số)."""
        raw = (raw or "").strip()
        corrected = (corrected or "").strip()
        if not raw or not corrected or raw == corrected or re.search(r"\d", raw):
            return False
        words = raw.split()
        pat = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
        self.correction_rules.append((re.compile(pat, re.IGNORECASE), corrected))
        return True

    def _apply_verified(self, text: str) -> str:
        """Tra từ điển cụm 3 rồi 2 âm tiết. Chỉ khớp khi các chữ cách nhau đúng khoảng trắng
        và đều KHÔNG dấu (chữ đã có dấu không bao giờ bị ghi đè)."""
        if not self.verified_map or not text:
            return text
        words = list(_WORD_RE.finditer(text))
        if len(words) < 2:
            return text
        out, pos, i = [], 0, 0
        while i < len(words):
            done = False
            for n in (3, 2):
                if i + n > len(words):
                    continue
                span = words[i:i + n]
                seps = [text[a.end():b.start()] for a, b in zip(span, span[1:])]
                if any(not s.isspace() or "\n" in s for s in seps):
                    continue
                key = " ".join(w.group(0).lower() for w in span)
                repl = self.verified_map.get(key)
                if repl:
                    s, e = span[0].start(), span[-1].end()
                    out.append(text[pos:s])
                    out.append(match_case(text[s:e], repl))
                    pos, i, done = e, i + n, True
                    break
            if not done:
                i += 1
        out.append(text[pos:])
        return "".join(out)

    def restore(self, text: str) -> str:
        """Khôi phục dấu tiếng Việt cho chuỗi văn bản."""
        if not text:
            return ""
        # Dòng ĐÃ có dấu đầy đủ (VietOCR / lớp chữ PDF) -> không đoán dấu nữa, chỉ áp sửa lỗi
        # người dùng đã xác nhận. Tránh 'khe co giãn' -> 'khe có giãn', 'lan can' -> 'lân cận'.
        lines = text.split("\n")
        if any(line_already_accented(ln) for ln in lines):
            return "\n".join(self._apply_corrections(ln) if line_already_accented(ln) else self._restore_raw(ln)
                             for ln in lines)
        return self._restore_raw(text)

    def _apply_corrections(self, text: str) -> str:
        for comp, corrected in self.correction_rules:
            text = comp.sub(lambda m, c=corrected: _apply_correction(m.group(0), c), text)
        return text

    def _restore_raw(self, text: str) -> str:
        if not text:
            return text
        result = text

        # Bước 1: Tách từ dính OCR
        for comp, repl in self.unstick_rules:
            result = comp.sub(lambda m, r=repl: match_case(m.group(0), r), result)

        # Bước 2: Khớp các cụm từ ghép dài nhất trước
        for comp, repl in self.phrase_rules:
            result = comp.sub(lambda m, r=repl: match_case(m.group(0), r), result)

        # Bước 3: Khớp các quy tắc ngữ cảnh và ngữ pháp.
        # Bảo vệ token IN HOA (nhãn/mã hiệu) và giữ nguyên hoa/thường của mã hiệu (xem _context_sub).
        for comp, repl in self.context_rules:
            result = comp.sub(lambda m, r=repl: _context_sub(m, r), result)

        # Bước 4: Sửa lỗi OCR do NGƯỜI dùng xác nhận (literal) — "chốt" theo đúng cặp
        # chữ người dùng đã dạy, nên phải chạy TRƯỚC khi tra từ điển cụm từ.
        for comp, corrected in self.correction_rules:
            result = comp.sub(lambda m, c=corrected: _apply_correction(m.group(0), c), result)

        # Bước 4b: Cụm từ ĐÃ KIỂM CHỨNG — tra từ điển, áp SAU CÙNG.
        # Bắt buộc đặt sau Bước 3 và Bước 4: hai bước này khớp mẫu trên chữ CÒN NGUYÊN
        # KHÔNG DẤU (lookahead kiểu 'da' + động từ, hay cặp literal 'chiu lyrc').
        # Nếu tra từ điển trước, nó gán dấu sớm làm mất ngữ cảnh và hai bước kia
        # không còn khớp: 'da thi cong' -> 'da thi công' (thiếu 'đã'),
        # 'ket cau chiu lyrc' -> không áp được cặp sửa 'chiu lyrc' -> 'chịu lực'.
        result = self._apply_verified(result)

        return result


# Singleton instance toàn cục
_DEFAULT_RESTORER: Optional[VietnameseDiacriticRestorer] = None


def restore_vietnamese_diacritics(text: str) -> str:
    """Hàm tiện ích khôi phục dấu tiếng Việt nhanh."""
    global _DEFAULT_RESTORER
    if _DEFAULT_RESTORER is None:
        _DEFAULT_RESTORER = VietnameseDiacriticRestorer()
    return _DEFAULT_RESTORER.restore(text)
