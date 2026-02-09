"""みんはや風 回答表示ウィンドウ"""

from __future__ import annotations
import customtkinter as ctk
from typing import Callable

from ui.styles import (
    MINHAYA_BG, MINHAYA_BG_CARD, MINHAYA_PURPLE, MINHAYA_PURPLE_DARK,
    MINHAYA_GOLD, MINHAYA_TEXT, MINHAYA_TEXT_DIM,
    MINHAYA_GREEN, MINHAYA_RED, MINHAYA_ORANGE,
    FONT_QUESTION, FONT_ANSWER, FONT_ANSWER_READING,
    FONT_STATUS, FONT_LABEL, FONT_BUTTON, FONT_SMALL,
)


class AnswerWindow:
    """みんはや風の回答ウィンドウ"""

    def __init__(self, root: ctk.CTk, *,
                 x: int, y: int, w: int, h: int,
                 on_start_stop: Callable[[], None] | None = None,
                 on_reset: Callable[[], None] | None = None,
                 on_settings: Callable[[], None] | None = None,
                 on_geometry_change: Callable[[int, int, int, int], None] | None = None):
        self._on_start_stop = on_start_stop
        self._on_reset = on_reset
        self._on_settings = on_settings
        self._on_geometry_change = on_geometry_change

        self._win = ctk.CTkToplevel(root)
        self._win.title("みんはやソルバー v2.0")
        self._win.geometry(f"{w}x{h}+{x}+{y}")
        self._win.configure(fg_color=MINHAYA_BG)
        self._win.minsize(400, 280)

        self._win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._win.bind("<Configure>", self._on_configure)
        self._close_callback: Callable[[], None] | None = None

        self._build_ui()

    # --- UI構築 ---

    def _build_ui(self):
        win = self._win

        # --- ヘッダー ---
        header = ctk.CTkFrame(win, fg_color=MINHAYA_PURPLE, corner_radius=0, height=38)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="みんはやソルバー",
            font=(FONT_LABEL[0], 14, "bold"),
            text_color=MINHAYA_TEXT,
        ).pack(side="left", padx=12)

        self._engine_label = ctk.CTkLabel(
            header, text="Gemini", font=FONT_SMALL, text_color=MINHAYA_GOLD,
        )
        self._engine_label.pack(side="right", padx=12)

        # --- 問題文エリア ---
        q_frame = ctk.CTkFrame(win, fg_color=MINHAYA_BG_CARD, corner_radius=10)
        q_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            q_frame, text="問題", font=FONT_SMALL,
            text_color=MINHAYA_TEXT_DIM,
        ).pack(anchor="w", padx=12, pady=(8, 0))

        self._question_label = ctk.CTkLabel(
            q_frame, text="キャプチャを開始してください",
            font=FONT_QUESTION, text_color=MINHAYA_TEXT,
            wraplength=460, justify="left",
        )
        self._question_label.pack(anchor="w", padx=12, pady=(2, 10))

        # --- 回答エリア ---
        a_frame = ctk.CTkFrame(win, fg_color=MINHAYA_PURPLE_DARK, corner_radius=10)
        a_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            a_frame, text="回答", font=FONT_SMALL,
            text_color=MINHAYA_GOLD,
        ).pack(anchor="w", padx=12, pady=(8, 0))

        self._answer_label = ctk.CTkLabel(
            a_frame, text="---",
            font=FONT_ANSWER, text_color=MINHAYA_GOLD,
            wraplength=460, justify="left",
        )
        self._answer_label.pack(anchor="w", padx=12, pady=(0, 4))

        self._reading_label = ctk.CTkLabel(
            a_frame, text="",
            font=FONT_ANSWER_READING, text_color=MINHAYA_TEXT_DIM,
        )
        self._reading_label.pack(anchor="w", padx=12, pady=(0, 10))

        # --- 信頼度バー ---
        bar_frame = ctk.CTkFrame(win, fg_color="transparent")
        bar_frame.pack(fill="x", padx=10, pady=(2, 0))

        self._confidence_bar = ctk.CTkProgressBar(
            bar_frame, height=6, corner_radius=3,
            fg_color=MINHAYA_BG_CARD,
            progress_color=MINHAYA_GREEN,
        )
        self._confidence_bar.pack(fill="x")
        self._confidence_bar.set(0)

        # --- ステータス ---
        status_frame = ctk.CTkFrame(win, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(4, 0))

        self._status_label = ctk.CTkLabel(
            status_frame, text="停止中",
            font=FONT_STATUS, text_color=MINHAYA_TEXT_DIM,
        )
        self._status_label.pack(side="left")

        self._timer_label = ctk.CTkLabel(
            status_frame, text="",
            font=FONT_STATUS, text_color=MINHAYA_TEXT_DIM,
        )
        self._timer_label.pack(side="right")

        # --- ボタン ---
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(8, 10))

        self._start_btn = ctk.CTkButton(
            btn_frame, text="開始",
            font=FONT_BUTTON, width=100, height=36,
            fg_color=MINHAYA_GREEN, hover_color="#388E3C",
            text_color=MINHAYA_TEXT,
            command=self._on_start_stop_click,
        )
        self._start_btn.pack(side="left", padx=(0, 6))

        self._reset_btn = ctk.CTkButton(
            btn_frame, text="リセット",
            font=FONT_BUTTON, width=100, height=36,
            fg_color=MINHAYA_ORANGE, hover_color="#F57C00",
            text_color=MINHAYA_TEXT,
            command=self._on_reset_click,
        )
        self._reset_btn.pack(side="left", padx=(0, 6))

        self._settings_btn = ctk.CTkButton(
            btn_frame, text="設定",
            font=FONT_BUTTON, width=70, height=36,
            fg_color=MINHAYA_BG_CARD, hover_color="#3A2F5E",
            text_color=MINHAYA_TEXT,
            command=self._on_settings_click,
        )
        self._settings_btn.pack(side="right")

    # --- public API ---

    def set_question(self, text: str):
        self._question_label.configure(text=text if text else "キャプチャを開始してください")

    def set_answer(self, text: str, reading: str = ""):
        self._answer_label.configure(text=text if text else "---")
        self._reading_label.configure(text=reading)

    def set_confidence(self, value: float):
        """0.0 ~ 1.0"""
        clamped = max(0.0, min(1.0, value))
        self._confidence_bar.set(clamped)
        if clamped > 0.7:
            color = MINHAYA_GREEN
        elif clamped > 0.4:
            color = MINHAYA_ORANGE
        else:
            color = MINHAYA_RED
        self._confidence_bar.configure(progress_color=color)

    def set_status(self, text: str, color: str = MINHAYA_TEXT_DIM):
        self._status_label.configure(text=text, text_color=color)

    def set_timer(self, text: str):
        self._timer_label.configure(text=text)

    def set_running(self, running: bool):
        if running:
            self._start_btn.configure(text="停止", fg_color=MINHAYA_RED, hover_color="#D32F2F")
        else:
            self._start_btn.configure(text="開始", fg_color=MINHAYA_GREEN, hover_color="#388E3C")

    def set_engine_name(self, name: str):
        self._engine_label.configure(text=name)

    def set_close_callback(self, cb: Callable[[], None]):
        self._close_callback = cb

    def destroy(self):
        self._win.destroy()

    # --- callbacks ---

    def _on_start_stop_click(self):
        if self._on_start_stop:
            self._on_start_stop()

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
