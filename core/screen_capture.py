"""mss ベースのスクリーンキャプチャ"""

from __future__ import annotations

import mss
from PIL import Image


_sct = None


def _get_sct():
    global _sct
    if _sct is None:
        _sct = mss.mss()
    return _sct


def grab_region(x: int, y: int, w: int, h: int) -> Image.Image:
    """指定矩形のスクリーンショットを PIL Image (RGB) で返す"""
    sct = _get_sct()
    shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def cleanup():
    global _sct
    if _sct is not None:
        _sct.close()
        _sct = None
