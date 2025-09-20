import os
from PIL import Image

# lấy thư mục gốc hiện tại
root = os.getcwd()

# duyệt đệ quy
for dirpath, _, filenames in os.walk(root):
    for file in filenames:
        if file.lower().endswith(".png"):
            png_path = os.path.join(dirpath, file)
            ico_path = os.path.splitext(png_path)[0] + ".ico"
            try:
                img = Image.open(png_path)
                img.save(ico_path, format="ICO")
                print(f"✔ Đã convert: {png_path} -> {ico_path}")
            except Exception as e:
                print(f"✘ Lỗi khi xử lý {png_path}: {e}")
