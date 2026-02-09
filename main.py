#!/usr/bin/env python3
"""みんはやソルバー v2.0 — CustomTkinter GUI (Gemini Vision)"""

import os
import sys
import time

import customtkinter as ctk
from dotenv import load_dotenv

# .env をロード
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from config import ConfigStore
from constants import MINHAYA_GREEN, MINHAYA_TEXT_DIM, MINHAYA_ORANGE
from core.screen_capture import grab_region, cleanup as cleanup_capture
from core.image_diff import images_similar
from core.ai_engine import GeminiVisionEngine, AsyncAIRunner, AIResult
from ui.capture_window import CaptureWindow
from ui.answer_window import AnswerWindow
from ui.settings_dialog import SettingsDialog


class MinhayaSolverApp:
    """メインオーケストレーター

    - after() でキャプチャループを駆動（tkinter メインスレッド）
    - AI 推論のみバックグラウンドスレッド
    """

    def __init__(self):
        self._config = ConfigStore()

        # --- CustomTkinter 設定 ---
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 非表示のルートウィンドウ
        self._root = ctk.CTk()
        self._root.withdraw()

        # --- AI エンジン (Gemini Vision のみ) ---
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            print("[ERROR] GEMINI_API_KEY が設定されていません (.env を確認)")
            sys.exit(1)
        self._gemini = GeminiVisionEngine(api_key)
        self._runner = AsyncAIRunner()

        # --- 状態 ---
        self._running = False
        self._last_image = None
        self._last_api_time = 0.0
        self._start_time = 0.0
        self._poll_id: str | None = None

        # --- ウィンドウ ---
        cap_rect = self._config.get_capture_rect()
        self._capture_win = CaptureWindow(
            self._root,
            x=cap_rect["x"], y=cap_rect["y"],
            w=cap_rect["w"], h=cap_rect["h"],
            on_geometry_change=self._on_capture_geometry,
        )

        ans_rect = self._config.get_answer_window_rect()
        self._answer_win = AnswerWindow(
            self._root,
            x=ans_rect["x"], y=ans_rect["y"],
            w=ans_rect["w"], h=ans_rect["h"],
            on_start_stop=self._toggle_running,
            on_reset=self._reset,
            on_settings=self._open_settings,
            on_geometry_change=self._on_answer_geometry,
        )
        self._answer_win.set_close_callback(self._quit)
        self._answer_win.set_engine_name("Gemini Vision")

        # --- キーボードショートカット ---
        self._root.bind_all("<Command-Shift-KeyPress-s>", lambda e: self._toggle_running())
        self._root.bind_all("<Command-Shift-KeyPress-r>", lambda e: self._reset())

    # ------------------------------------------------------------------
    # 開始 / 停止 / リセット
    # ------------------------------------------------------------------

    def _toggle_running(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._running = True
        self._start_time = time.time()
        self._answer_win.set_running(True)
        self._answer_win.set_status("稼働中", MINHAYA_GREEN)
        self._capture_win.set_active(True)
        self._schedule_tick()

    def _stop(self):
        self._running = False
        if self._poll_id:
            self._root.after_cancel(self._poll_id)
            self._poll_id = None
        self._answer_win.set_running(False)
        self._answer_win.set_status("停止中", MINHAYA_TEXT_DIM)
        self._capture_win.set_active(False)

    def _reset(self):
        self._stop()
        self._last_image = None
        self._last_api_time = 0.0
        self._answer_win.set_question("")
        self._answer_win.set_answer("")
        self._answer_win.set_confidence(0)
        self._answer_win.set_timer("")
        self._answer_win.set_status("停止中", MINHAYA_TEXT_DIM)

    # ------------------------------------------------------------------
    # メインループ（after ベース）
    # ------------------------------------------------------------------

    def _schedule_tick(self):
        if not self._running:
            return
        interval = self._config.capture_interval_ms
        self._poll_id = self._root.after(interval, self._tick)

    def _tick(self):
        if not self._running:
            return

        # タイマー更新
        elapsed = time.time() - self._start_time
        self._answer_win.set_timer(f"{elapsed:.0f}s")

        # AI 結果をポーリング
        result = self._runner.poll()
        if result is not None:
            self._handle_ai_result(result)

        # キャプチャ（枠を一瞬隠して撮影）
        try:
            x, y, w, h = self._capture_win.get_region()
            if w > 4 and h > 4:
                self._capture_win.hide()
                image = grab_region(x, y, w, h)
                self._capture_win.show()
                self._process_image(image)
        except Exception as e:
            self._capture_win.show()
            self._answer_win.set_status(f"キャプチャエラー: {e}", MINHAYA_ORANGE)

        self._schedule_tick()

    # ------------------------------------------------------------------
    # 画像処理 → AI 送信
    # ------------------------------------------------------------------

    def _process_image(self, image):
        # 画像変化チェック
        if images_similar(image, self._last_image):
            return

        self._last_image = image.copy()

        # API 間隔チェック
        now = time.time()
        if now - self._last_api_time < self._config.api_interval:
            return

        if self._runner.busy:
            return

        self._last_api_time = now
        self._answer_win.set_status("Gemini に問い合わせ中...", MINHAYA_ORANGE)
        self._runner.submit_image(self._gemini, image)

    def _handle_ai_result(self, result: AIResult):
        if result.error:
            self._answer_win.set_status(f"エラー: {result.error[:60]}", MINHAYA_ORANGE)
            self._answer_win.set_confidence(0.0)
            return

        answer = result.answer
        # 回答とよみがなを分離 (例: "織田信長（おだのぶなが）")
        reading = ""
        if "（" in answer and "）" in answer:
            idx = answer.index("（")
            reading = answer[idx + 1:answer.index("）")]
            main_answer = answer[:idx]
        elif "(" in answer and ")" in answer:
            idx = answer.index("(")
            reading = answer[idx + 1:answer.index(")")]
            main_answer = answer[:idx]
        else:
            main_answer = answer

        self._answer_win.set_answer(main_answer, reading)
        self._answer_win.set_confidence(0.8)
        self._answer_win.set_status("稼働中", MINHAYA_GREEN)

    # ------------------------------------------------------------------
    # 設定
    # ------------------------------------------------------------------

    def _open_settings(self):
        was_running = self._running
        if was_running:
            self._stop()
        SettingsDialog(
            self._answer_win._win, self._config,
            on_save=lambda cfg: self._on_settings_saved(cfg, was_running),
        )

    def _on_settings_saved(self, cfg: ConfigStore, restart: bool):
        if restart:
            self._start()

    # ------------------------------------------------------------------
    # ジオメトリ永続化
    # ------------------------------------------------------------------

    def _on_capture_geometry(self, x: int, y: int, w: int, h: int):
        self._config.set_capture_rect(x, y, w, h)

    def _on_answer_geometry(self, x: int, y: int, w: int, h: int):
        self._config.set_answer_window_rect(x, y, w, h)

    # ------------------------------------------------------------------
    # 終了
    # ------------------------------------------------------------------

    def _quit(self):
        self._stop()
        cleanup_capture()
        self._capture_win.destroy()
        self._root.quit()

    # ------------------------------------------------------------------
    # 起動
    # ------------------------------------------------------------------

    def run(self):
        self._root.mainloop()


def main():
    app = MinhayaSolverApp()
    app.run()


if __name__ == "__main__":
    main()
