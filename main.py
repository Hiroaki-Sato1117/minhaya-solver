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

# デバッグ用: キャプチャ画像の保存先
DEBUG_DIR = os.path.expanduser("~/Desktop/minhaya_debug")

# キャプチャループ間隔 (ms)
_CAPTURE_TICK_MS = 50


class MinhayaSolverApp:
    """メインオーケストレーター

    操作フロー:
    1. キャプチャ枠を配置
    2. 「キャプチャ開始」→ 画面撮影が始まる
    3. 問題が来たら「AI開始」→ Gemini に連続送信
    4. 問題が終わったら「AI停止」→ API課金ストップ
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
        self._capturing = False           # キャプチャON/OFF
        self._api_active = False          # AI送信ON/OFF
        self._latest_image = None         # 最新のキャプチャ画像
        self._last_sent_image = None      # 最後にAPIに送った画像
        self._start_time = 0.0
        self._poll_id: str | None = None
        self._api_send_count = 0
        # 前回の推測（累積コンテキスト）
        self._prev_answer = ""
        self._prev_confidence = 0  # 0-100

        # --- デバッグディレクトリ ---
        os.makedirs(DEBUG_DIR, exist_ok=True)

        # --- ウィンドウ ---
        cap_rect = self._config.get_capture_rect()
        self._capture_win = CaptureWindow(
            self._root,
            x=cap_rect["x"], y=cap_rect["y"],
            w=cap_rect["w"], h=cap_rect["h"],
            on_geometry_change=self._on_capture_geometry,
            on_focus_release=self._focus_answer_window,
        )
        self._capture_win.set_active(False)

        ans_rect = self._config.get_answer_window_rect()
        self._answer_win = AnswerWindow(
            self._root,
            x=ans_rect["x"], y=ans_rect["y"],
            w=ans_rect["w"], h=ans_rect["h"],
            on_capture_toggle=self._toggle_capture,
            on_ai_toggle=self._toggle_api,
            on_reset=self._reset,
            on_settings=self._open_settings,
            on_geometry_change=self._on_answer_geometry,
        )
        self._answer_win.set_close_callback(self._quit)

        # --- キーボードショートカット ---
        self._root.bind_all("<Command-Shift-KeyPress-c>", lambda e: self._toggle_capture())
        self._root.bind_all("<Command-Shift-KeyPress-s>", lambda e: self._toggle_api())
        self._root.bind_all("<Command-Shift-KeyPress-r>", lambda e: self._reset())

    # ------------------------------------------------------------------
    # キャプチャ ON/OFF
    # ------------------------------------------------------------------

    def _toggle_capture(self):
        if self._capturing:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        self._capturing = True
        self._capture_win.set_active(True)
        self._answer_win.set_capture_active(True)
        self._answer_win.set_status("キャプチャ中 — AI開始を押してください", "#1565C0")
        self._schedule_tick()

    def _stop_capture(self):
        # AI も止める
        if self._api_active:
            self._stop_api()
        self._capturing = False
        if self._poll_id:
            self._root.after_cancel(self._poll_id)
            self._poll_id = None
        self._capture_win.set_active(False)
        self._answer_win.set_capture_active(False)
        self._answer_win.set_status("キャプチャ停止", MINHAYA_TEXT_DIM)
        self._answer_win.set_timer("")

    # ------------------------------------------------------------------
    # AI送信 ON/OFF
    # ------------------------------------------------------------------

    def _toggle_api(self):
        if not self._capturing:
            return  # キャプチャ中でないとAIは使えない
        if self._api_active:
            self._stop_api()
        else:
            self._start_api()

    def _start_api(self):
        self._api_active = True
        self._start_time = time.time()
        self._api_send_count = 0
        self._answer_win.set_api_active(True)
        self._answer_win.set_status("AI送信中", MINHAYA_GREEN)
        # 即座に最新画像を送信
        self._try_send_api()

    def _stop_api(self):
        self._api_active = False
        self._answer_win.set_api_active(False)
        if self._capturing:
            self._answer_win.set_status("キャプチャ中 — AI停止", "#1565C0")
        else:
            self._answer_win.set_status("停止", MINHAYA_TEXT_DIM)
        self._answer_win.set_timer("")

    def _reset(self):
        self._stop_api()
        self._last_sent_image = None
        self._prev_answer = ""
        self._prev_confidence = 0
        self._answer_win.set_answer("")
        self._answer_win.set_confidence(0)
        if self._capturing:
            self._answer_win.set_status("キャプチャ中 — AI開始を押してください", "#1565C0")
        else:
            self._answer_win.set_status("キャプチャ枠を配置してください", MINHAYA_TEXT_DIM)

    # ------------------------------------------------------------------
    # メインループ（50ms tick）
    # ------------------------------------------------------------------

    def _schedule_tick(self):
        if not self._capturing:
            return
        self._poll_id = self._root.after(_CAPTURE_TICK_MS, self._tick)

    def _tick(self):
        if not self._capturing:
            return

        # AI 結果をポーリング
        result = self._runner.poll()
        if result is not None:
            self._handle_ai_result(result)
            # パイプライン: 結果が返ったら即座に次を送信
            if self._api_active:
                self._try_send_api()

        # タイマー更新
        if self._api_active:
            elapsed = time.time() - self._start_time
            self._answer_win.set_timer(f"{elapsed:.0f}s")

        # キャプチャ（枠を一瞬隠して撮影）
        try:
            x, y, w, h = self._capture_win.get_region()
            if w > 4 and h > 4:
                self._capture_win.hide()
                image = grab_region(x, y, w, h)
                self._capture_win.show()
                self._latest_image = image
        except Exception:
            self._capture_win.show()

        # API アクティブかつ空いていたら送信
        if self._api_active and not self._runner.busy:
            self._try_send_api()

        self._schedule_tick()

    # ------------------------------------------------------------------
    # API送信（パイプライン方式）
    # ------------------------------------------------------------------

    def _try_send_api(self):
        if not self._api_active:
            return
        if self._runner.busy:
            return
        if self._latest_image is None:
            return

        # 同じ画像は送らない
        if images_similar(self._latest_image, self._last_sent_image):
            return

        self._last_sent_image = self._latest_image.copy()
        self._api_send_count += 1
        self._answer_win.set_status(
            f"AI問い合わせ中... (#{self._api_send_count})", MINHAYA_ORANGE)

        # デバッグ: 最初の3枚 + 以後10枚ごと
        if self._api_send_count <= 3 or self._api_send_count % 10 == 0:
            path = os.path.join(DEBUG_DIR, f"api_{self._api_send_count:04d}.png")
            self._latest_image.save(path)
            print(f"[DEBUG] API送信 #{self._api_send_count}: {path}")

        self._runner.submit_image(
            self._gemini, self._latest_image,
            prev_answer=self._prev_answer,
            prev_confidence=self._prev_confidence,
        )

    # ------------------------------------------------------------------
    # AI結果ハンドリング
    # ------------------------------------------------------------------

    def _handle_ai_result(self, result: AIResult):
        if result.error:
            self._answer_win.set_status(f"エラー: {result.error[:80]}", MINHAYA_ORANGE)
            self._answer_win.set_confidence(0.0)
            print(f"[DEBUG] AI エラー: {result.error}")
            return

        answer = result.answer
        confidence = result.confidence
        print(f"[DEBUG] Gemini 回答: '{answer}' 確信度: {confidence:.0%}")

        # 不明の場合
        if answer == "不明":
            self._answer_win.set_answer("不明")
            self._answer_win.set_confidence(0.0)
            if self._api_active:
                self._answer_win.set_status("AI送信中 — 解答不明", MINHAYA_ORANGE)
            self._prev_answer = ""
            self._prev_confidence = 0
            return

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

        # 前回の推測を保存
        self._prev_answer = main_answer + (f"（{reading}）" if reading else "")
        self._prev_confidence = int(confidence * 100)

        self._answer_win.set_answer(main_answer, reading)
        self._answer_win.set_confidence(confidence)
        if self._api_active:
            self._answer_win.set_status(
                f"AI送信中 — 確信度 {confidence:.0%}", MINHAYA_GREEN)

    # ------------------------------------------------------------------
    # 設定
    # ------------------------------------------------------------------

    def _open_settings(self):
        was_api = self._api_active
        was_cap = self._capturing
        if was_api:
            self._stop_api()
        if was_cap:
            self._stop_capture()
        SettingsDialog(
            self._answer_win._win, self._config,
            on_save=lambda cfg: self._on_settings_saved(cfg, was_cap, was_api),
        )

    def _on_settings_saved(self, cfg: ConfigStore, restart_cap: bool, restart_api: bool):
        if restart_cap:
            self._start_capture()
        if restart_api:
            self._start_api()

    # ------------------------------------------------------------------
    # フォーカス管理
    # ------------------------------------------------------------------

    def _focus_answer_window(self):
        try:
            self._answer_win._win.lift()
            self._answer_win._win.focus_force()
        except Exception:
            pass

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
        if self._api_active:
            self._stop_api()
        if self._capturing:
            self._stop_capture()
        if self._poll_id:
            self._root.after_cancel(self._poll_id)
        cleanup_capture()
        self._capture_win.destroy()
        self._root.quit()

    # ------------------------------------------------------------------
    # 起動
    # ------------------------------------------------------------------

    def run(self):
        print(f"[INFO] デバッグ画像保存先: {DEBUG_DIR}")
        print(f"[INFO] Cmd+Shift+C: キャプチャ開始/停止")
        print(f"[INFO] Cmd+Shift+S: AI送信 開始/停止")
        print(f"[INFO] Cmd+Shift+R: リセット")
        self._root.mainloop()


def main():
    app = MinhayaSolverApp()
    app.run()


if __name__ == "__main__":
    main()
