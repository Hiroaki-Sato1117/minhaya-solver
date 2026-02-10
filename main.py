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
        self._capture_count = 0
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

        ans_rect = self._config.get_answer_window_rect()
        self._answer_win = AnswerWindow(
            self._root,
            x=ans_rect["x"], y=ans_rect["y"],
            w=ans_rect["w"], h=ans_rect["h"],
            on_start_stop=self._toggle_running,
            on_reset=self._reset,
            on_settings=self._open_settings,
            on_test_capture=self._test_capture,
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
        self._capture_count = 0
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
        self._prev_answer = ""
        self._prev_confidence = 0
        self._answer_win.set_question("")
        self._answer_win.set_answer("")
        self._answer_win.set_confidence(0)
        self._answer_win.set_timer("")
        self._answer_win.set_status("停止中", MINHAYA_TEXT_DIM)

    # ------------------------------------------------------------------
    # テストキャプチャ（デバッグ用）
    # ------------------------------------------------------------------

    def _test_capture(self):
        """現在のキャプチャ領域を1枚撮影してデスクトップに保存"""
        try:
            x, y, w, h = self._capture_win.get_region()
            print(f"[DEBUG] キャプチャ領域: x={x}, y={y}, w={w}, h={h}")
            self._answer_win.set_status(f"テスト: ({x},{y}) {w}x{h}", MINHAYA_ORANGE)

            if w < 4 or h < 4:
                self._answer_win.set_status("エラー: キャプチャ領域が小さすぎます", MINHAYA_ORANGE)
                return

            # alpha=0 で撮影
            self._capture_win.hide()
            image = grab_region(x, y, w, h)
            self._capture_win.show()

            # デスクトップに保存
            path = os.path.join(DEBUG_DIR, f"test_capture_{int(time.time())}.png")
            image.save(path)
            print(f"[DEBUG] テストキャプチャ保存: {path}")
            print(f"[DEBUG] 画像サイズ: {image.size}, モード: {image.mode}")

            # 画像の明るさチェック
            import numpy as np
            arr = np.array(image)
            mean_brightness = arr.mean()
            print(f"[DEBUG] 平均輝度: {mean_brightness:.1f} (0=真っ黒, 255=真っ白)")

            self._answer_win.set_status(
                f"保存: ~/Desktop/minhaya_debug/ 輝度:{mean_brightness:.0f}",
                MINHAYA_GREEN,
            )
            self._answer_win.set_question(
                f"テストキャプチャ完了\n領域: ({x},{y}) {w}×{h}px\n"
                f"画像: {image.size[0]}×{image.size[1]}px  輝度: {mean_brightness:.0f}"
            )

        except Exception as e:
            self._answer_win.set_status(f"テストエラー: {e}", MINHAYA_ORANGE)
            print(f"[DEBUG] テストキャプチャエラー: {e}")
            import traceback
            traceback.print_exc()

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
        self._capture_count += 1

        # デバッグ: 最初の3枚 + その後は10枚ごとに保存
        if self._capture_count <= 3 or self._capture_count % 10 == 0:
            path = os.path.join(DEBUG_DIR, f"cap_{self._capture_count:04d}.png")
            image.save(path)
            print(f"[DEBUG] キャプチャ #{self._capture_count} 保存: {path}")

        # 適応的API間隔: 確信度が低い → より頻繁に問い合わせ
        now = time.time()
        base_interval = self._config.api_interval
        if self._prev_confidence >= 80:
            # 高確信度 → 間隔を伸ばす（ほぼ確定なので節約）
            interval = base_interval * 2.0
        elif self._prev_confidence >= 50:
            interval = base_interval
        else:
            # 低確信度 → 最短間隔で積極的に更新
            interval = base_interval * 0.5

        if now - self._last_api_time < interval:
            return

        if self._runner.busy:
            return

        self._last_api_time = now
        self._answer_win.set_status("Gemini に問い合わせ中...", MINHAYA_ORANGE)

        # API に送る画像も保存
        api_path = os.path.join(DEBUG_DIR, f"api_send_{int(now)}.png")
        image.save(api_path)
        print(f"[DEBUG] API送信画像: {api_path} (前回: {self._prev_answer} {self._prev_confidence}%)")

        self._runner.submit_image(
            self._gemini, image,
            prev_answer=self._prev_answer,
            prev_confidence=self._prev_confidence,
        )

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
            self._answer_win.set_status("稼働中 — 解答不明", MINHAYA_ORANGE)
            # 不明の場合は前回コンテキストをクリアして再挑戦
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

        # 前回の推測を保存（次回APIで累積コンテキストとして使用）
        self._prev_answer = main_answer + (f"（{reading}）" if reading else "")
        self._prev_confidence = int(confidence * 100)

        self._answer_win.set_answer(main_answer, reading)
        self._answer_win.set_confidence(confidence)
        self._answer_win.set_status(f"稼働中 — 確信度 {confidence:.0%}", MINHAYA_GREEN)

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
    # フォーカス管理
    # ------------------------------------------------------------------

    def _focus_answer_window(self):
        """キャプチャウィンドウ操作後、回答ウィンドウにフォーカスを戻す"""
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
        self._stop()
        cleanup_capture()
        self._capture_win.destroy()
        self._root.quit()

    # ------------------------------------------------------------------
    # 起動
    # ------------------------------------------------------------------

    def run(self):
        print(f"[INFO] デバッグ画像保存先: {DEBUG_DIR}")
        print(f"[INFO] Cmd+Shift+S: 開始/停止  Cmd+Shift+R: リセット")
        self._root.mainloop()


def main():
    app = MinhayaSolverApp()
    app.run()


if __name__ == "__main__":
    main()
