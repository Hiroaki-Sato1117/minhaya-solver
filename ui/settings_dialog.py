"""設定ダイアログ"""

from __future__ import annotations
import customtkinter as ctk
from typing import Callable

from config import ConfigStore
from ui.styles import (
    MINHAYA_BG, MINHAYA_BG_CARD, MINHAYA_PURPLE,
    MINHAYA_TEXT, MINHAYA_TEXT_DIM, MINHAYA_GOLD,
    MINHAYA_GREEN,
    FONT_LABEL, FONT_BUTTON, FONT_SMALL,
)


class SettingsDialog:
    """設定ダイアログ"""

    def __init__(self, parent, config: ConfigStore, *,
                 on_save: Callable[[ConfigStore], None] | None = None):
        self._config = config
        self._on_save = on_save

        self._dialog = ctk.CTkToplevel(parent)
        self._dialog.title("設定")
        self._dialog.geometry("360x240")
        self._dialog.configure(fg_color=MINHAYA_BG)
        self._dialog.attributes("-topmost", True)
        self._dialog.resizable(False, False)
        self._dialog.grab_set()

        self._build_ui()

    def _build_ui(self):
        d = self._dialog

        # --- API 間隔 ---
        ctk.CTkLabel(
            d, text="API 呼び出し間隔（秒）", font=FONT_LABEL, text_color=MINHAYA_TEXT,
        ).pack(anchor="w", padx=16, pady=(20, 4))

        self._interval_var = ctk.DoubleVar(value=self._config.api_interval)
        interval_frame = ctk.CTkFrame(d, fg_color="transparent")
        interval_frame.pack(fill="x", padx=16)

        self._interval_slider = ctk.CTkSlider(
            interval_frame, from_=1, to=10,
            variable=self._interval_var,
            fg_color=MINHAYA_BG_CARD,
            progress_color=MINHAYA_PURPLE,
            button_color=MINHAYA_GOLD,
            button_hover_color=MINHAYA_GOLD,
            width=240,
        )
        self._interval_slider.pack(side="left")

        self._interval_label = ctk.CTkLabel(
            interval_frame, text=f"{self._config.api_interval:.1f}s",
            font=FONT_SMALL, text_color=MINHAYA_TEXT_DIM, width=40,
        )
        self._interval_label.pack(side="left", padx=(8, 0))
        self._interval_var.trace_add("write", self._on_interval_change)

        # --- キャプチャ間隔 ---
        ctk.CTkLabel(
            d, text="キャプチャ間隔（ms）", font=FONT_LABEL, text_color=MINHAYA_TEXT,
        ).pack(anchor="w", padx=16, pady=(20, 4))

        self._cap_interval_var = ctk.IntVar(value=self._config.capture_interval_ms)
        cap_frame = ctk.CTkFrame(d, fg_color="transparent")
        cap_frame.pack(fill="x", padx=16)

        self._cap_slider = ctk.CTkSlider(
            cap_frame, from_=100, to=1000,
            variable=self._cap_interval_var,
            fg_color=MINHAYA_BG_CARD,
            progress_color=MINHAYA_PURPLE,
            button_color=MINHAYA_GOLD,
            button_hover_color=MINHAYA_GOLD,
            width=240,
        )
        self._cap_slider.pack(side="left")

        self._cap_label = ctk.CTkLabel(
            cap_frame, text=f"{self._config.capture_interval_ms}ms",
            font=FONT_SMALL, text_color=MINHAYA_TEXT_DIM, width=50,
        )
        self._cap_label.pack(side="left", padx=(8, 0))
        self._cap_interval_var.trace_add("write", self._on_cap_interval_change)

        # --- ボタン ---
        btn_frame = ctk.CTkFrame(d, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(24, 16))

        ctk.CTkButton(
            btn_frame, text="保存", font=FONT_BUTTON,
            fg_color=MINHAYA_GREEN, hover_color="#388E3C",
            text_color=MINHAYA_TEXT,
            width=100, height=34,
            command=self._save,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="キャンセル", font=FONT_BUTTON,
            fg_color=MINHAYA_BG_CARD, hover_color="#3A2F5E",
            text_color=MINHAYA_TEXT,
            width=100, height=34,
            command=self._cancel,
        ).pack(side="left")

    def _on_interval_change(self, *_):
        try:
            val = self._interval_var.get()
            self._interval_label.configure(text=f"{val:.1f}s")
        except Exception:
            pass

    def _on_cap_interval_change(self, *_):
        try:
            val = self._cap_interval_var.get()
            self._cap_label.configure(text=f"{int(val)}ms")
        except Exception:
            pass

    def _save(self):
        self._config.set("api_interval", round(self._interval_var.get(), 1))
        self._config.set("capture_interval_ms", int(self._cap_interval_var.get()))
        if self._on_save:
            self._on_save(self._config)
        self._dialog.destroy()

    def _cancel(self):
        self._dialog.destroy()
