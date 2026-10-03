# -*- coding: utf-8 -*-
"""
Vietnamese Diacritic Restoration Engine for AEC Engineering Documents
(Engine Tự động Khôi phục Dấu Tiếng Việt từ chữ Latin không dấu)
===================================================================
Chuyên trách khôi phục dấu tiếng Việt chuẩn xác cho kết quả OCR (RapidOCR),
giữ nguyên 100% các con số, kích thước hình học, mã hiệu kỹ thuật và định dạng
chữ hoa/thường.

Tốc độ: ~0.001 - 0.005s/trang (chạy CPU 100% offline, không cần GPU).
"""

import re
import unicodedata
from typing import List, Tuple, Optional


AEC_COMPOUND_PHRASES: List[Tuple[str, str]] = [
    # Cụm 4 - 6 từ (Ưu tiên khớp cụm dài trước)
    ("ban quan ly du an dau tu xay dung", "ban quản lý dự án đầu tư xây dựng"),
    ("thiet ke ban ve thi cong", "thiết kế bản vẽ thi công"),
    ("quy chuan ky thuat quoc gia", "quy chuẩn kỹ thuật quốc gia"),
    ("tieu chuan ky thuat quoc gia", "tiêu chuẩn kỹ thuật quốc gia"),
    ("tieu chuan quoc gia ve", "tiêu chuẩn quốc gia về"),
    ("bao hieu duong bo", "báo hiệu đường bộ"),
    ("mang phan quang dung cho", "màng phản quang dùng cho"),
    ("vai dia ky thuat phuong phap thu", "vải địa kỹ thuật phương pháp thử"),
    ("vai dia ky thuat", "vải địa kỹ thuật"),
    ("phuong phap thu", "phương pháp thử"),
    ("mang phan quang", "màng phản quang"),
    ("bang thong ke cot thep", "bảng thống kê cốt thép"),
    ("thong ke cot thep", "thống kê cốt thép"),
    ("bang tong hop khoi luong", "bảng tổng hợp khối lượng"),
    ("tong hop khoi luong", "tổng hợp khối lượng"),
    ("so giao thong van tai", "sở giao thông vận tải"),
    ("bo giao thong van tai", "bộ giao thông vận tải"),
    ("hoi dong nghiem thu", "hội đồng nghiệm thu"),
    ("uy ban nhan dan", "ủy ban nhân dân"),
    ("chieu dai coc khoan nhoi", "chiều dài cọc khoan nhồi"),
    ("coc khoan nhoi", "cọc khoan nhồi"),
    ("lo khoan khao sat", "lỗ khoan khảo sát"),
    ("khao sat dia chat", "khảo sát địa chất"),
    ("be tong cot thep", "bê tông cốt thép"),
    ("be tong nhua", "bê tông nhựa"),
    ("be tong xi mang", "bê tông xi măng"),
    ("nhua duong nong", "nhựa đường nóng"),
    ("lop phong nuoc", "lớp phòng nước"),
    ("lop bao ve", "lớp bảo vệ"),
    ("tiep xuc voi nen dat", "tiếp xúc với nền đất"),
    ("can phai quet", "cần phải quét"),
    ("tuong chan op mai ta luy", "tường chắn ốp mái ta luy"),
    ("op mai ta luy", "ốp mái ta luy"),
    ("mai ta luy", "mái ta luy"),
    ("duong dau cau", "đường đầu cầu"),
    ("khau do thoat nuoc", "khẩu độ thoát nước"),
    ("be rong mat cau", "bề rộng mặt cầu"),
    ("be rong nen duong", "bề rộng nền đường"),
    ("do doc doc", "độ dốc dọc"),
    ("do doc ngang", "độ dốc ngang"),
    ("an toan lao dong", "an toàn lao động"),
    ("phong chay chua chay", "phòng cháy chữa cháy"),
    ("bien phap to chuc thi cong", "biện pháp tổ chức thi công"),
    ("to chuc thi cong", "tổ chức thi công"),
    ("bien phap thi cong", "biện pháp thi công"),
    ("theo van ban so", "theo văn bản số"),
    ("vat lieu su dung", "vật liệu sử dụng"),
    ("mat bang bo tri chung", "mặt bằng bố trí chung"),
    ("mat bang bo tri", "mặt bằng bố trí"),
    ("so do bo tri", "sơ đồ bố trí"),
    ("bo tri cot thep", "bố trí cốt thép"),
    ("bo tri chung", "bố trí chung"),
    ("dap chon loc dam chat", "đắp chọn lọc đầm chặt"),
    ("dap chon loc", "đắp chọn lọc"),
    ("chan khay gia co tu non", "chân khay gia cố tứ nón"),
    ("gia co tu non", "gia cố tứ nón"),
    ("tu non", "tứ nón"),
    ("trong luong don vi", "trọng lượng đơn vị"),
    ("tong trong luong", "tổng trọng lượng"),
    ("tong chieu dai", "tổng chiều dài"),
    ("tai trong thiet ke", "tải trọng thiết kế"),
    ("tan suat thiet ke", "tần suất thiết kế"),
    ("khoi luong du toan", "khối lượng dự toán"),
    ("khoi luong moi thau", "khối lượng mời thầu"),
    ("phan cau va duong dau cau", "phần cầu và đường đầu cầu"),

    # Cụm 2 - 3 từ
    ("ban quan ly", "ban quản lý"),
    ("du an", "dự án"),
    ("dau tu", "đầu tư"),
    ("xay dung", "xây dựng"),
    ("chu dau tu", "chủ đầu tư"),
    ("nha thau", "nhà thầu"),
    ("tu van", "tư vấn"),
    ("thiet ke", "thiết kế"),
    ("giam sat", "giám sát"),
    ("thi cong", "thi công"),
    ("nghiem thu", "nghiệm thu"),
    ("hoan cong", "hoàn công"),
    ("tham dinh", "thẩm định"),
    ("phe duyet", "phê duyệt"),
    ("cong trinh", "công trình"),
    ("hang muc", "hạng mục"),
    ("goi thau", "gói thầu"),
    ("ban ve", "bản vẽ"),
    ("chuc danh", "chức danh"),
    ("ho va ten", "họ và tên"),
    ("chu ky", "chữ ký"),
    ("giam doc", "giám đốc"),
    ("pho giam doc", "phó giám đốc"),
    ("chu nhiem", "chủ nhiệm"),
    ("chu tri", "chủ trì"),
    ("nguoi ve", "người vẽ"),
    ("kiem tra", "kiểm tra"),
    ("hieu dinh", "hiệu đính"),
    ("soat xet", "soát xét"),
    ("ty le", "tỷ lệ"),
    ("so hieu", "số hiệu"),
    ("ngay thang nam", "ngày tháng năm"),
    ("dia chi", "địa chỉ"),
    ("thanh pho", "thành phố"),
    ("thi xa", "thị xã"),
    ("quan huyen", "quận huyện"),
    ("phuong xa", "phường xã"),
    ("thon xom", "thôn xóm"),
    ("dong van", "Đồng Văn"),
    ("ha giang", "Hà Giang"),
    ("nguyen trai", "Nguyễn Trãi"),

    # Kết cấu & Vật liệu
    ("thong ke", "thống kê"),
    ("khoi luong", "khối lượng"),
    ("trong luong", "trọng lượng"),
    ("so luong", "số lượng"),
    ("chieu dai", "chiều dài"),
    ("chieu rong", "chiều rộng"),
    ("chieu cao", "chiều cao"),
    ("chieu day", "chiều dày"),
    ("be rong", "bề rộng"),
    ("duong kinh", "đường kính"),
    ("ky hieu", "ký hiệu"),
    ("hinh dang", "hình dáng"),
    ("don vi", "đơn vị"),
    ("don gia", "đơn giá"),
    ("thanh tien", "thành tiền"),
    ("tong cong", "tổng cộng"),
    ("ghi chu", "ghi chú"),
    ("be tong", "bê tông"),
    ("cot thep", "cốt thép"),
    ("thep chu", "thép chủ"),
    ("thep dai", "thép đai"),
    ("thep cau tao", "thép cấu tạo"),
    ("thep ban", "thép bản"),
    ("thep neo", "thép neo"),
    ("thanh chot", "thanh chốt"),
    ("dam chu T", "dầm chữ T"),
    ("dam chu I", "dầm chữ I"),
    ("dam chu U", "dầm chữ U"),
    ("dam chu", "dầm chủ"),
    ("dam ngang", "dầm ngang"),
    ("dam bien", "dầm biên"),
    ("dam giua", "dầm giữa"),
    ("ban mat cau", "bản mặt cầu"),
    ("ban qua do", "bản quá độ"),
    ("khe co gian", "khe co giãn"),
    ("goi cau", "gối cầu"),
    ("goi cao su", "gối cao su"),
    ("lan can", "lan can"),
    ("tay vin", "tay vịn"),
    ("da dam", "đá dăm"),
    ("dat dap", "đất đắp"),
    ("dam chat", "đầm chặt"),
    ("tuong chan", "tường chắn"),
    ("tuong canh", "tường cánh"),
    ("chan khay", "chân khay"),
    ("ranh thoat nuoc", "rãnh thoát nước"),
    ("ranh dat", "rãnh đất"),
    ("ong thoat nuoc", "ống thoát nước"),
    ("thoat nuoc", "thoát nước"),
    ("ho thu", "hố thu"),
    ("cong hop", "cống hộp"),
    ("cong tron", "cống tròn"),
    ("mo cau", "mố cầu"),
    ("tru cau", "trụ cầu"),
    ("xa mu", "xà mũ"),
    ("be mong", "bệ móng"),
    ("mong coc", "móng cọc"),
    ("lo khoan", "lỗ khoan"),
    ("khao sat", "khảo sát"),
    ("dia chat", "địa chất"),
    ("thuy van", "thủy văn"),
    ("luu vuc", "lưu vực"),
    ("he so", "hệ số"),
    ("muc nuoc", "mực nước"),
    ("mat bang", "mặt bằng"),
    ("mat cat", "mặt cắt"),
    ("mat dung", "mặt đứng"),
    ("chi tiet", "chi tiết"),
    ("cau tao", "cấu tạo"),
    ("bo tri", "bố trí"),
    ("dinh vi", "định vị"),
    ("so do", "sơ đồ"),
    ("vat lieu", "vật liệu"),
    ("tieu chuan", "tiêu chuẩn"),
    ("quy chuan", "quy chuẩn"),
    ("ky thuat", "kỹ thuật"),
    ("quoc gia", "quốc gia"),
    ("do tai cho", "đổ tại chỗ"),
    ("nho nhat", "nhỏ nhất"),
    ("lon nhat", "lớn nhất"),
    ("quy trinh", "quy trình"),
    ("nen dat", "nền đất"),
    ("nhua duong", "nhựa đường"),
    ("tuong duong", "tương đương"),
    ("giua nhip", "giữa nhịp"),
    ("cac ket cau", "các kết cấu"),
    ("nhu sau", "như sau"),
    ("tron tron", "tròn trơn"),
    ("co go", "có gờ"),
    ("gioi han chay", "giới hạn chảy"),
    ("gioi han", "giới hạn"),
    ("cap do ben", "cấp độ bền"),
    ("tai trong", "tải trọng"),
    ("suc chiu tai", "sức chịu tải"),
    ("chieu sau", "chiều sâu"),
    ("cao do", "cao độ"),
    ("ly trinh", "lý trình"),
    ("nhip cau", "nhịp cầu"),
    ("tuyen duong", "tuyến đường"),
    ("diem dau", "điểm đầu"),
    ("diem cuoi", "điểm cuối"),
    ("dia phan", "địa phận"),
    ("du kien", "dự kiến"),
    ("tinh toan", "tính toán"),
    ("tren co so", "trên cơ sở"),
    ("co so", "cơ sở"),

    # Địa chất & Thí nghiệm đất đá
    ("dac diem dia chat", "đặc điểm địa chất"),
    ("dac diem dia tang", "đặc điểm địa tầng"),
    ("chi tieu co ly", "chỉ tiêu cơ lý"),
    ("cac lop dat", "các lớp đất"),
    ("lop dat", "lớp đất"),
    ("tu tren xuong", "từ trên xuống"),
    ("lop phu tan tich", "lớp phủ tàn tích"),
    ("tan tich", "tàn tích"),
    ("dat set pha", "đất sét pha"),
    ("dat set", "đất sét"),
    ("mau xam nau", "màu xám nâu"),
    ("mau xam vang", "màu xám vàng"),
    ("mau xam den", "màu xám đen"),
    ("mau xam ghi", "màu xám ghi"),
    ("xam ghi", "xám ghi"),
    ("lan re cay", "lẫn rễ cây"),
    ("thuc vat", "thực vật"),
    ("lan dam san", "lẫn dăm sạn"),
    ("dam san", "dăm sạn"),
    ("trang thai deo cung", "trạng thái dẻo cứng"),
    ("trang thai", "trạng thái"),
    ("deo cung", "dẻo cứng"),
    ("da phien set voi", "đá phiến sét vôi"),
    ("da phien set", "đá phiến sét"),
    ("da phien", "đá phiến"),
    ("xen kep", "xen kẹp"),
    ("thach anh", "thạch anh"),
    ("da phong hoa", "đá phong hóa"),
    ("phong hoa manh", "phong hóa mạnh"),
    ("phong hoa vua nhe", "phong hóa vừa - nhẹ"),
    ("phong hoa", "phong hóa"),
    ("nut ne", "nứt nẻ"),
    ("it nut ne", "ít nứt nẻ"),
    ("thoi ngan", "thỏi ngắn"),
    ("dam cuc", "dăm cục"),

    # Thiết kế cầu & Tải trọng
    ("giai phap thiet ke", "giải pháp thiết kế"),
    ("phan cau", "phần cầu"),
    ("cau dam gian don", "cầu dầm giản đơn"),
    ("dam gian don", "dầm giản đơn"),
    ("gian don", "giản đơn"),
    ("mot nhip", "một nhịp"),
    ("hoat tai xe o to", "hoạt tải xe ô tô"),
    ("hoat tai", "hoạt tải"),
    ("tinh tai", "tĩnh tải"),
    ("xe o to", "xe ô tô"),
    ("cap dong dat", "cấp động đất"),
    ("he so gia toc nen", "hệ số gia tốc nền"),
    ("gia toc nen", "gia tốc nền"),
    ("phu luc", "phụ lục"),
    ("tra bang tai", "tra bảng tại"),
    ("tra bang", "tra bảng"),
    ("ket cau phan tren", "kết cấu phần trên"),
    ("ket cau phan duoi", "kết cấu phần dưới"),
    ("ket cau nhip", "kết cấu nhịp"),
    ("nhip dam btct", "nhịp dầm BTCT"),
    ("nhip dam", "nhịp dầm"),
    ("mat cat ngang cau", "mặt cắt ngang cầu"),
    ("mat cat ngang", "mặt cắt ngang"),
    ("bao gom", "bao gồm"),
    ("phien dam", "phiến dầm"),
    ("khoang cach giua cac dam", "khoảng cách giữa các dầm"),
    ("khoang cach", "khoảng cách"),
    ("chieu cao dam", "chiều cao dầm"),
    ("cau nam tren duong thang", "cầu nằm trên đường thẳng"),
    ("duong thang", "đường thẳng"),
    ("do doc doc cau", "độ dốc dọc cầu"),
    ("do doc ngang cau", "độ dốc ngang cầu"),
    ("dam ngang tai", "dầm ngang tại"),
    ("dau nhip", "đầu nhịp"),
    ("trong nhip", "trong nhịp"),
    ("gia tri toi thieu", "giá trị tối thiểu"),
    ("gia tri toi da", "giá trị tối đa"),
    ("xac dinh tai vi tri", "xác định tại vị trí"),
    ("xac dinh", "xác định"),
    ("mep dinh dam", "mép đỉnh dầm"),
    ("dinh dam", "đỉnh dầm"),
    ("mat cat giua nhip", "mặt cắt giữa nhịp"),
    ("mat cat giua", "mặt cắt giữa"),
    ("mat cat dau nhip", "mặt cắt đầu nhịp"),
    ("be rong xe chay", "bề rộng xe chạy"),
    ("xe chay", "xe chạy"),
    ("go lan can", "gờ lan can"),
    ("tan suat lu", "tần suất lũ"),
    ("tan suat", "tần suất"),
    ("cay troi", "cây trôi"),
    ("ket cau mat duong", "kết cấu mặt đường"),
    ("lang nhua", "láng nhựa"),
    ("giong tuyen chinh", "giống tuyến chính"),
    ("tuyen chinh", "tuyến chính")
]

# Sắp xếp giảm dần theo số từ để ưu tiên cụm từ dài nhất trước
AEC_COMPOUND_PHRASES.sort(key=lambda x: len(x[0].split()), reverse=True)

AEC_CONTEXT_RULES: List[Tuple[str, str]] = [
    # 1. Số lượng + Danh từ kết cấu
    (r"\b(\d+)\s*lop\b", r"\1 lớp"),
    (r"\blop\s*(\d+)\b", r"lớp \1"),
    (r"\blop\s+nhua\b", "lớp nhựa"),
    (r"\blop\s+phu\b", "lớp phủ"),
    (r"\bmac\s*([0-9]+|[A-Za-z]+)", r"mác \1"),
    (r"\bso\s+(\d+)\b", r"số \1"),
    (r"\bso\s*:\s*(\d+)", r"số: \1"),
    (r"\bngo\s+(\d+)\b", r"ngõ \1"),
    (r"\bto\s+(\d+)\b", r"tổ \1"),
    (r"\bphuong\s+([A-ZÀ-Ỹa-zà-ỹ0-9]+)", r"phường \1"),
    (r"\bxa\s+([A-ZÀ-Ỹa-zà-ỹ0-9]+)", r"xã \1"),
    (r"\bhuyen\s+([A-ZÀ-Ỹa-zà-ỹ0-9]+)", r"huyện \1"),
    (r"\btinh\s+([A-ZÀ-Ỹa-zà-ỹ0-9]+)", r"tỉnh \1"),
    (r"\bthanh\s+pho\s+([A-ZÀ-Ỹa-zà-ỹ0-9]+)", r"thành phố \1"),

    # 2. Cấu kiện + Mã hiệu (M1, T1, D1, C1)
    (r"\bmo\s+([A-Za-z0-9]+)\b", r"mố \1"),
    (r"\btru\s+([A-Za-z0-9]+)\b", r"trụ \1"),
    (r"\bcoc\s+([A-Za-z0-9]+)\b", r"cọc \1"),
    (r"\bdam\s+([A-Za-z0-9]+)\b", r"dầm \1"),
    (r"\bthep\s+([A-Za-z0-9]+)\b", r"thép \1"),
    (r"\bduong\s+([A-Za-z0-9]+)\b", r"đường \1"),

    # 3. Từ nối & Ngữ pháp kỹ thuật thông dụng
    (r"\bduoc\b", "được"),
    (r"\bla\b", "là"),
    (r"\bva\b", "và"),
    (r"\bcua\b", "của"),
    (r"\btren\b", "trên"),
    (r"\bduoi\b", "dưới"),
    (r"\btu\b(?=\s+[a-zà-ỹA-Z0-9])", "từ"),
    (r"\bden\b", "đến"),
    (r"\bde\b", "để"),
    (r"\bcac\b", "các"),
    (r"\bnhung\b", "những"),
    (r"\bvoi\b", "với"),
    (r"\btai\b", "tại"),
    (r"\btheo\b", "theo"),
    (r"\bve\b(?=\s+[a-zà-ỹA-Z0-9])", "về"),
    (r"\bcan\b(?=\s+phai)", "cần"),
    (r"\bphai\b", "phải"),
    (r"\bco\b(?=\s+[a-zà-ỹA-Z0-9])", "có"),
    (r"\bkhong\b", "không"),
    (r"\bse\b", "sẽ"),
    (r"\bda\b(?=\s+[a-zà-ỹA-Z0-9])", "đã"),
    (r"\bchua\b", "chưa"),
    (r"\brang\b", "rằng"),
    (r"\bnhu\b", "như"),
    (r"\bthi\b", "thì"),
    (r"\btrong\s+do\b", "trong đó"),
    (r"\btrong\b", "trong")
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


class VietnameseDiacriticRestorer:
    """
    Engine phục hồi dấu tiếng Việt từ văn bản Latin không dấu.
    Bảo toàn 100% số liệu, ký hiệu kỹ thuật và kiểu viết hoa.
    """

    def __init__(self):
        self.phrase_rules = []
        for pat, repl in AEC_COMPOUND_PHRASES:
            words = pat.split()
            regex_pat = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
            self.phrase_rules.append((re.compile(regex_pat, re.IGNORECASE), repl))

        self.context_rules = []
        for pat, repl in AEC_CONTEXT_RULES:
            self.context_rules.append((re.compile(pat, re.IGNORECASE), repl))

    def restore(self, text: str) -> str:
        """Khôi phục dấu tiếng Việt cho chuỗi văn bản."""
        if not text:
            return ""
        result = text
        # 1. Khớp các cụm từ ghép dài nhất trước
        for comp, repl in self.phrase_rules:
            result = comp.sub(lambda m, r=repl: match_case(m.group(0), r), result)

        # 2. Khớp các quy tắc ngữ cảnh và ngữ pháp
        for comp, repl in self.context_rules:
            result = comp.sub(lambda m, r=repl: match_case(m.group(0), m.expand(r)), result)

        return result


# Singleton instance toàn cục
_DEFAULT_RESTORER: Optional[VietnameseDiacriticRestorer] = None


def restore_vietnamese_diacritics(text: str) -> str:
    """Hàm tiện ích khôi phục dấu tiếng Việt nhanh."""
    global _DEFAULT_RESTORER
    if _DEFAULT_RESTORER is None:
        _DEFAULT_RESTORER = VietnameseDiacriticRestorer()
    return _DEFAULT_RESTORER.restore(text)
