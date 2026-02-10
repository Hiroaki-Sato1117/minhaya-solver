"""みんはや風 回答表示ウィンドウ"""

from __future__ import annotations
import customtkinter as ctk
from typing import Callable

from ui.styles import (
    MINHAYA_BG, MINHAYA_BG_CARD, MINHAYA_PURPLE, MINHAYA_PURPLE_DARK,
    MINHAYA_GOLD, MINHAYA_TEXT, MINHAYA_TEXT_DIM,
    MINHAYA_GREEN, MINHAYA_RED, MINHAYA_ORANGE,
    FONT_FAMILY,
    FONT_QUESTION, FONT_ANSWER, FONT_ANSWER_READING,
    FONT_STATUS, FONT_LABEL, FONT_BUTTON, FONT_SMALL,
)


class AnswerWindow:
    """回答表示ウィンドウ

    ボタン: キャプチャ開始/停止、AI開始/停止、リセット、設定
    """

    def __init__(self, root: ctk.CTk, *,
                 x: int, y: int, w: int, h: int,
                 on_capture_toggle: Callable[[], None] | None = None,
                 on_ai_toggle: Callable[[], None] | None = None,
                 on_reset: Callable[[], None] | None = None,
                 on_settings: Callable[[], None] | None = None,
                 on_geometry_change: Callable[[int, int, int, int], None] | None = None):
        self._on_capture_toggle = on_capture_toggle
        self._on_ai_toggle = on_ai_toggle
        self._on_reset = on_reset
        self._on_settings = on_settings
        self._on_geometry_change = on_geometry_change

        self._win = ctk.CTkToplevel(root)
        self._win.title("みんはやソルバー v2.0")
        self._win.geometry(f"{w}x{h}+{x}+{y}")
        self._win.configure(fg_color=MINHAYA_BG)
        self._win.minsize(380, 300)

        self._win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._win.bind("<Configure>", self._on_configure)
        self._close_callback: Callable[[], None] | None = None

        self._build_ui()

    # --- UI構築 ---

    def _build_ui(self):
        win = self._win

        # ============================================================
        # ボタン・ステータスを BOTTOM から先に pack（見切れ防止）
        # ============================================================

        # --- ボタン行（2段） ---

        # 下段: リセット + 設定
        btn_row2 = ctk.CTkFrame(win, fg_color="transparent")
        btn_row2.pack(side="bottom", fill="x", padx=10, pady=(2, 10))

        self._reset_btn = ctk.CTkButton(
            btn_row2, text="リセット",
            font=FONT_BUTTON, width=80, height=30,
            fg_color=MINHAYA_ORANGE, hover_color="#F57C00",
            text_color=MINHAYA_TEXT,
            command=self._on_reset_click,
        )
        self._reset_btn.pack(side="left", padx=(0, 6))

        self._settings_btn = ctk.CTkButton(
            btn_row2, text="設定",
            font=FONT_BUTTON, width=60, height=30,
            fg_color=MINHAYA_BG_CARD, hover_color="#3A2F5E",
            text_color=MINHAYA_TEXT,
            command=self._on_settings_click,
        )
        self._settings_btn.pack(side="right")

        # 上段: キャプチャ開始 + AI開始（メインボタン）
        btn_row1 = ctk.CTkFrame(win, fg_color="transparent")
        btn_row1.pack(side="bottom", fill="x", padx=10, pady=(4, 0))

        self._capture_btn = ctk.CTkButton(
            btn_row1, text="キャプチャ開始",
            font=(FONT_FAMILY, 13, "bold"), width=140, height=40,
            fg_color="#1565C0", hover_color="#0D47A1",
            text_color=MINHAYA_TEXT,
            command=self._on_capture_click,
        )
        self._capture_btn.pack(side="left", padx=(0, 6))

        self._ai_btn = ctk.CTkButton(
            btn_row1, text="AI開始",
            font=(FONT_FAMILY, 15, "bold"), width=140, height=40,
            fg_color=MINHAYA_GREEN, hover_color="#388E3C",
            text_color=MINHAYA_TEXT,
            command=self._on_ai_click,
            state="disabled",
        )
        self._ai_btn.pack(side="left")

        # --- ステータス ---
        status_frame = ctk.CTkFrame(win, fg_color="transparent")
        status_frame.pack(side="bottom", fill="x", padx=12, pady=(2, 0))

        self._status_label = ctk.CTkLabel(
            status_frame, text="キャプチャ枠を配置してください",
            font=FONT_STATUS, text_color=MINHAYA_TEXT_DIM,
        )
        self._status_label.pack(side="left")

        self._timer_label = ctk.CTkLabel(
            status_frame, text="",
            font=FONT_STATUS, text_color=MINHAYA_TEXT_DIM,
        )
        self._timer_label.pack(side="right")

        # --- 信頼度パーセンテージ（大きく表示） ---
        pct_frame = ctk.CTkFrame(win, fg_color="transparent")
        pct_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 2))

        ctk.CTkLabel(
            pct_frame, text="確信度",
            font=FONT_STATUS, text_color=MINHAYA_TEXT_DIM,
        ).pack(side="left")

        self._confidence_pct = ctk.CTkLabel(
            pct_frame, text="0%",
            font=(FONT_FAMILY, 28, "bold"), text_color=MINHAYA_TEXT_DIM,
        )
        self._confidence_pct.pack(side="right")

        # --- 信頼度バー ---
        bar_frame = ctk.CTkFrame(win, fg_color="transparent")
        bar_frame.pack(side="bottom", fill="x", padx=10, pady=(2, 0))

        self._confidence_bar = ctk.CTkProgressBar(
            bar_frame, height=10, corner_radius=5,
            fg_color=MINHAYA_BG_CARD,
            progress_color=MINHAYA_GREEN,
        )
        self._confidence_bar.pack(fill="x")
        self._confidence_bar.set(0)

        # ============================================================
        # 回答エリア（メイン — 残り全スペースを使って大きく表示）
        # ============================================================

        a_frame = ctk.CTkFrame(win, fg_color=MINHAYA_PURPLE_DARK, corner_radius=10)
        a_frame.pack(fill="both", expand=True, padx=10, pady=(6, 4))

        self._answer_label = ctk.CTkLabel(
            a_frame, text="---",
            font=(FONT_FAMILY, 42, "bold"), text_color=MINHAYA_GOLD,
            wraplength=460, justify="center",
        )
        self._answer_label.pack(expand=True, padx=16, pady=(12, 4))

        self._reading_label = ctk.CTkLabel(
            a_frame, text="",
            font=(FONT_FAMILY, 18), text_color=MINHAYA_TEXT_DIM,
        )
        self._reading_label.pack(padx=16, pady=(0, 12))

    # --- public API ---

    def set_answer(self, text: str, reading: str = ""):
        self._answer_label.configure(text=text if text else "---")
        self._reading_label.configure(text=reading)

    def set_confidence(self, value: float):
        """0.0 ~ 1.0"""
        clamped = max(0.0, min(1.0, value))
        self._confidence_bar.set(clamped)
        self._confidence_pct.configure(text=f"{clamped:.0%}")
        if clamped > 0.7:
            color = MINHAYA_GREEN
        elif clamped > 0.4:
            color = MINHAYA_ORANGE
        else:
            color = MINHAYA_RED
        self._confidence_bar.configure(progress_color=color)
        self._confidence_pct.configure(text_color=color)

    def set_status(self, text: str, color: str = MINHAYA_TEXT_DIM):
        self._status_label.configure(text=text, text_color=color)

    def set_timer(self, text: str):
        self._timer_label.configure(text=text)

    def set_capture_active(self, active: bool):
        if active:
            self._capture_btn.configure(
                text="キャプチャ停止", fg_color="#B71C1C", hover_color="#D32F2F")
            # キャプチャ中ならAIボタンを有効化
            self._ai_btn.configure(state="normal")
        else:
            self._capture_btn.configure(
                text="キャプチャ開始", fg_color="#1565C0", hover_color="#0D47A1")
            # キャプチャ停止中はAIボタンを無効化
            self._ai_btn.configure(state="disabled")

    def set_api_active(self, active: bool):
        if active:
            self._ai_btn.configure(
                text="AI停止", fg_color=MINHAYA_RED, hover_color="#D32F2F")
        else:
            self._ai_btn.configure(
                text="AI開始", fg_color=MINHAYA_GREEN, hover_color="#388E3C")

    def set_close_callback(self, cb: Callable[[], None]):
        self._close_callback = cb

    def destroy(self):
        self._win.destroy()

    # --- callbacks ---

    def _on_capture_click(self):
        if self._on_capture_toggle:
            self._on_capture_toggle()

    def _on_ai_click(self):
        if self._on_ai_toggle:
            self._on_ai_toggle()

    def _on_reset_click(self):
        if self._on_reset:
            self._on_reset()

    def _on_settings_click(self):
        if self._on_settings:
            self._on_settings()

    def _on_close(self):
        if self._close_callback:
            self._close_callback()

    def _on_configure(self, event):
        if self._on_geometry_change and event.widget == self._win:
            try:
                x = self._win.winfo_x()
                y = self._win.winfo_y()
                w = self._win.winfo_width()
                h = self._win.winfo_height()
                self._on_geometry_change(x, y, w, h)
            except Exception:
                pass
