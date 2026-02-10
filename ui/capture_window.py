"""キャプチャオーバーレイウィンドウ

半透明ウィンドウ + 太い枠線。
辺をドラッグでリサイズ、中央ドラッグで移動。
キャプチャ時は alpha=0.0 にして下の画面を撮影する。
"""

from __future__ import annotations
import time
import tkinter as tk
from typing import Callable

from constants import (
    CAPTURE_BORDER_WIDTH, CAPTURE_MIN_W, CAPTURE_MIN_H, RESIZE_HANDLE_SIZE,
    CAPTURE_BORDER_COLOR, CAPTURE_BORDER_ACTIVE,
)

# 枠の太さ（つかみやすいように太め）
_BORDER = 10
# リサイズ判定のハンドル領域（辺のどこでも掴めるよう広めに）
_HANDLE = 30
# 通常時の透過度
_NORMAL_ALPHA = 0.35


class CaptureWindow:
    """半透明キャプチャオーバーレイ（ドラッグ移動+8方向リサイズ）"""

    def __init__(self, root: tk.Tk, *,
                 x: int, y: int, w: int, h: int,
                 on_geometry_change: Callable[[int, int, int, int], None] | None = None,
                 on_focus_release: Callable[[], None] | None = None):
        self._on_geometry_change = on_geometry_change
        self._on_focus_release = on_focus_release
        self._root = root

        self._win = tk.Toplevel(root)
        self._win.title("Capture")
        self._win.geometry(f"{w}x{h}+{x}+{y}")
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 1.0)

        # macOS: ウィンドウ背景を透明にする
        try:
            self._win.wm_attributes("-transparent", True)
        except Exception:
            pass

        # macOS: overrideredirect ウィンドウのフォーカス固着を防止
        try:
            self._win.tk.call("::tk::unsupported::MacWindowStyle",
                              "style", self._win._w, "plain", "none")
        except Exception:
            pass

        # Canvas（背景を systemTransparent に）
        self._canvas = tk.Canvas(
            self._win, highlightthickness=0, bg="systemTransparent",
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
        """キャプチャ前に完全透明にする（withdraw より高速・安定）"""
        self._win.attributes("-alpha", 0.0)
        self._win.update_idletasks()
        # macOS の WindowServer が反映するまで待機（最小限）
        time.sleep(0.02)

    def show(self):
        """キャプチャ後に復帰"""
        self._win.attributes("-alpha", 1.0)

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

        # 中央を透明に（枠だけ表示）
        c.create_rectangle(b, b, w - b, h - b, fill="systemTransparent", outline="")

        # 4辺の枠
        c.create_rectangle(0, 0, w, b, fill=border_color, outline="")       # 上
        c.create_rectangle(0, h - b, w, h, fill=border_color, outline="")   # 下
        c.create_rectangle(0, b, b, h - b, fill=border_color, outline="")   # 左
        c.create_rectangle(w - b, b, w, h - b, fill=border_color, outline="")  # 右

        # 四隅にハンドルマーク（L字型で掴みやすく表示）
        hs = _HANDLE
        ht = b + 2  # ハンドルの太さ
        for corner in ["nw", "ne", "sw", "se"]:
            if corner == "nw":
                c.create_rectangle(0, 0, hs, ht, fill=border_color, outline="")
                c.create_rectangle(0, 0, ht, hs, fill=border_color, outline="")
            elif corner == "ne":
                c.create_rectangle(w - hs, 0, w, ht, fill=border_color, outline="")
                c.create_rectangle(w - ht, 0, w, hs, fill=border_color, outline="")
            elif corner == "sw":
                c.create_rectangle(0, h - ht, hs, h, fill=border_color, outline="")
                c.create_rectangle(0, h - hs, ht, h, fill=border_color, outline="")
            elif corner == "se":
                c.create_rectangle(w - hs, h - ht, w, h, fill=border_color, outline="")
                c.create_rectangle(w - ht, h - hs, w, h, fill=border_color, outline="")

    # --- リサイズ端の判定 ---

    def _edge_at(self, ex: int, ey: int) -> str:
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        hs = _HANDLE  # 四隅のコーナー判定サイズ
        b = _BORDER   # ボーダー幅（ボーダー上なら必ずリサイズ）

        # コーナー判定（四隅は広めの領域で判定）
        top_corner = ey < hs
        bottom_corner = ey > h - hs
        left_corner = ex < hs
        right_corner = ex > w - hs

        if top_corner and left_corner:
            return "nw"
        if top_corner and right_corner:
            return "ne"
        if bottom_corner and left_corner:
            return "sw"
        if bottom_corner and right_corner:
            return "se"

        # 辺の判定（ボーダー幅 or ハンドル領域内なら辺リサイズ）
        on_top = ey < b
        on_bottom = ey > h - b
        on_left = ex < b
        on_right = ex > w - b

        if on_top:
            return "n"
        if on_bottom:
            return "s"
        if on_left:
            return "w"
        if on_right:
            return "e"

        # コーナー以外でもハンドル領域内なら辺リサイズ
        if top_corner:
            return "n"
        if bottom_corner:
            return "s"
        if left_corner:
            return "w"
        if right_corner:
            return "e"

        # 中央 → 移動
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
        # フォーカスを回答ウィンドウへ戻す
        if self._on_focus_release:
            self._win.after(50, self._on_focus_release)

    def _notify_change(self):
        if self._on_geometry_change:
            x, y, w, h = self.get_full_geometry()
            self._on_geometry_change(x, y, w, h)
