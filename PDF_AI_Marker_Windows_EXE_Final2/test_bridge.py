from marker_bridge import convert
from pathlib import Path

source = r"D:\Công ty 307\Cao tốc\Cầu\1. Bản vẽ\BPTC CKN CAUKM19+529.080.pdf"
dest = "test_output"
try:
    target, payload, markdown = convert(source, dest, mode='vn_ocr', pages='1')
    print("SUCCESS")
    print(markdown[:500])
except Exception as e:
    import traceback
    traceback.print_exc()
