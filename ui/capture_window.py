"""キャプチャオーバーレイウィンドウ

半透明ウィンドウ + 太い枠線。
辺をドラッグでリサイズ、中央ドラッグで移動。
キャプチャ時は一瞬非表示にして下の画面を撮影する。
"""

from __future__ import annotations
import tkinter as tk
from typing import Callable

from constants import (
    CAPTURE_BORDER_WIDTH, CAPTURE_MIN_W, CAPTURE_MIN_H, RESIZE_HANDLE_SIZE,
    CAPTURE_BORDER_COLOR, CAPTURE_BORDER_ACTIVE,
)

# 枠の太さ（つかみやすいように太め）
_BORDER = 6
# リサイズ判定のハンドル領域
_HANDLE = 16


class CaptureWindow:
    """半透明キャプチャオーバーレイ（ドラッグ移動+8方向リサイズ）"""

    def __init__(self, root: tk.Tk, *,
                 x: int, y: int, w: int, h: int,
                 on_geometry_change: Callable[[int, int, int, int], None] | None = None):
        self._on_geometry_change = on_geometry_change
        self._root = root

        self._win = tk.Toplevel(root)
        self._win.title("Capture")
        self._win.geometry(f"{w}x{h}+{x}+{y}")
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        # 半透明（枠は見える、中央は薄く透ける）
        self._win.attributes("-alpha", 0.35)

        # Canvas
        self._canvas = tk.Canvas(
            self._win, highlightthickness=0, bg="#000000",
        )
        self._canvas.pack(fill="both", expand=True)

        # 状態
        self._drag_data: dict = {}
        self._resize_edge: str = ""
        self._active = False

        # イベントバインド
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Motion>", self._on_hover)
        self._canvas.bind("<Configure>", lambda e: self._draw())

        self._draw()

    # --- public ---

    def get_region(self) -> tuple[int, int, int, int]:
        """枠内側のキャプチャ領域 (x, y, w, h) をスクリーン座標で返す"""
        self._win.update_idletasks()
        x = self._win.winfo_rootx()
        y = self._win.winfo_rooty()
        w = self._win.winfo_width()
        h = self._win.winfo_height()
        b = _BORDER
        return (x + b, y + b, max(1, w - b * 2), max(1, h - b * 2))

    def get_full_geometry(self) -> tuple[int, int, int, int]:
        self._win.update_idletasks()
        return (
            self._win.winfo_x(), self._win.winfo_y(),
            self._win.winfo_width(), self._win.winfo_height(),
        )

    def set_active(self, active: bool):
        self._active = active
        self._draw()

    def hide(self):
        """キャプチャ前に一瞬隠す"""
        self._win.withdraw()
        self._win.update_idletasks()

    def show(self):
        """キャプチャ後に復帰"""
        self._win.deiconify()
        self._win.attributes("-topmost", True)

    def destroy(self):
        self._win.destroy()

    # --- 描画 ---

    def _draw(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        b = _BORDER
        border_color = CAPTURE_BORDER_ACTIVE if self._active else CAPTURE_BORDER_COLOR

        # 中央を暗い半透明に（枠は明るい色）
        c.create_rectangle(b, b, w - b, h - b, fill="#111111", outline="")

        # 4辺の枠
        c.create_rectangle(0, 0, w, b, fill=border_color, outline="")       # 上
        c.create_rectangle(0, h - b, w, h, fill=border_color, outline="")   # 下
        c.create_rectangle(0, b, b, h - b, fill=border_color, outline="")   # 左
        c.create_rectangle(w - b, b, w, h - b, fill=border_color, outline="")  # 右

        # 四隅にハンドルマーク
        hs = _HANDLE
        for cx, cy in [(0, 0), (w - hs, 0), (0, h - hs), (w - hs, h - hs)]:
            c.create_rectangle(cx, cy, cx + hs, cy + hs,
                               fill=border_color, outline="")

    # --- リサイズ端の判定 ---

    def _edge_at(self, ex: int, ey: int) -> str:
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        hs = _HANDLE

        top = ey < hs
        bottom = ey > h - hs
        left = ex < hs
        right = ex > w - hs

        if top and left:
            return "nw"
        if top and right:
            return "ne"
        if bottom and left:
            return "sw"
        if bottom and right:
            return "se"
        if top:
            return "n"
        if bottom:
            return "s"
        if left:
            return "w"
        if right:
            return "e"
        return ""

    _CURSOR_MAP = {
        "n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
        "w": "sb_h_double_arrow", "e": "sb_h_double_arrow",
        "nw": "top_left_corner", "ne": "top_right_corner",
        "sw": "bottom_left_corner", "se": "bottom_right_corner",
        "": "fleur",
    }

    def _on_hover(self, event: tk.Event):
        edge = self._edge_at(event.x, event.y)
        self._canvas.config(cursor=self._CURSOR_MAP.get(edge, "fleur"))

    # --- ドラッグ / リサイズ ---

    def _on_press(self, event: tk.Event):
        self._resize_edge = self._edge_at(event.x, event.y)
        self._drag_data = {
            "sx": event.x_root, "sy": event.y_root,
            "wx": self._win.winfo_x(), "wy": self._win.winfo_y(),
            "ww": self._win.winfo_width(), "wh": self._win.winfo_height(),
        }

    def _on_motion(self, event: tk.Event):
        d = self._drag_data
        if not d:
            return
        dx = event.x_root - d["sx"]
        dy = event.y_root - d["sy"]
        edge = self._resize_edge

        if not edge:
            # 移動
            self._win.geometry(f"+{d['wx'] + dx}+{d['wy'] + dy}")
            return

        nx, ny, nw, nh = d["wx"], d["wy"], d["ww"], d["wh"]

        if "e" in edge:
            nw = max(CAPTURE_MIN_W, d["ww"] + dx)
        if "s" in edge:
            nh = max(CAPTURE_MIN_H, d["wh"] + dy)
        if "w" in edge:
            new_w = max(CAPTURE_MIN_W, d["ww"] - dx)
            nx = d["wx"] + d["ww"] - new_w
            nw = new_w
        if "n" in edge:
            new_h = max(CAPTURE_MIN_H, d["wh"] - dy)
            ny = d["wy"] + d["wh"] - new_h
            nh = new_h

        self._win.geometry(f"{nw}x{nh}+{nx}+{ny}")

    def _on_release(self, event: tk.Event):
        self._drag_data = {}
        self._resize_edge = ""
        self._notify_change()

    def _notify_change(self):
        if self._on_geometry_change:
            x, y, w, h = self.get_full_geometry()
            self._on_geometry_change(x, y, w, h)
