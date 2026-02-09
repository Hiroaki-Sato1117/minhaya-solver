"""画像変化検出"""

from PIL import Image
from constants import IMAGE_DIFF_THRESHOLD


def images_similar(img1: Image.Image | None,
                   img2: Image.Image | None,
                   threshold: float = IMAGE_DIFF_THRESHOLD) -> bool:
    """2つのPIL画像が似ているか判定（縮小→ピクセル比較）"""
    if img1 is None or img2 is None:
        return False
    if img1.size != img2.size:
        return False
    small1 = img1.resize((32, 32)).convert("L")
    small2 = img2.resize((32, 32)).convert("L")
    pixels1 = list(small1.getdata())
    pixels2 = list(small2.getdata())
    matches = sum(abs(p1 - p2) < 30 for p1, p2 in zip(pixels1, pixels2))
    return matches / len(pixels1) > threshold
