"""AI 推論エンジン（Claude / Gemini Vision）"""

from __future__ import annotations
import base64
import http.client
import io
import json
import ssl
import time
import threading
import urllib.request
from queue import Queue, Empty
from typing import Callable

from PIL import Image

from constants import (
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_PROMPT_TEMPLATE,
    GEMINI_MODEL, GEMINI_TIMEOUT, GEMINI_PROMPT,
    GEMINI_CONTEXT_TEMPLATE, GEMINI_CONTEXT_EMPTY,
    IMAGE_MAX_WIDTH, IMAGE_JPEG_QUALITY,
)

# SSL 検証を緩和
ssl._create_default_https_context = ssl._create_unverified_context


# === 結果オブジェクト ===

class AIResult:
    __slots__ = ("answer", "confidence", "error")
    def __init__(self, answer: str = "", confidence: float = 0.0, error: str = ""):
        self.answer = answer
        self.confidence = confidence  # 0.0 ~ 1.0
        self.error = error


# === エンジン実装 ===

class ClaudeEngine:
    """Anthropic Claude API（テキストのみ送信）"""

    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic()

    def ask(self, question: str) -> AIResult:
        try:
            resp = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[
                    {"role": "user",
                     "content": CLAUDE_PROMPT_TEMPLATE.format(question=question)}
                ],
            )
            return AIResult(answer=resp.content[0].text.strip())
        except Exception as e:
            return AIResult(error=str(e))


class GeminiVisionEngine:
    """Google Gemini API（画像を直接送信 — OCR 不要）"""

    _GEMINI_HOST = "generativelanguage.googleapis.com"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._local = threading.local()  # スレッドごとにKeep-Alive接続を保持

    def _get_conn(self) -> http.client.HTTPSConnection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = http.client.HTTPSConnection(self._GEMINI_HOST, timeout=GEMINI_TIMEOUT)
            self._local.conn = conn
        return conn

    @staticmethod
    def _optimize_image(image: Image.Image) -> tuple[bytes, str]:
        """画像をリサイズ+JPEG圧縮して転送サイズを削減"""
        img = image
        if img.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / img.width
            new_h = int(img.height * ratio)
            img = img.resize((IMAGE_MAX_WIDTH, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        rgb = img.convert("RGB") if img.mode != "RGB" else img
        rgb.save(buf, format="JPEG", quality=IMAGE_JPEG_QUALITY)
        return buf.getvalue(), "image/jpeg"

    @staticmethod
    def _parse_response(text: str) -> tuple[str, float]:
        """Gemini レスポンスから回答と確信度をパース"""
        import re
        confidence = 0.0
        conf_match = re.search(r'確信度\s*[:：]\s*(\d+)', text)
        if conf_match:
            confidence = min(100, max(0, int(conf_match.group(1)))) / 100.0

        answer = "不明"
        ans_match = re.search(r'答え\s*[:：]\s*(.+)', text)
        if ans_match:
            raw = ans_match.group(1).strip()
            raw = re.split(r'\n|確信度', raw)[0].strip()
        else:
            lines = text.strip().split('\n')
            raw = re.split(r'確信度', lines[0])[0].strip() if lines else ""

        if raw and len(raw) <= 30 and raw != "不明":
            answer = raw
        else:
            answer = "不明"
            confidence = 0.0
        if answer == "不明":
            confidence = 0.0
        return answer, confidence

    def ask_with_image(self, image: Image.Image,
                       prev_answer: str = "", prev_confidence: int = 0) -> AIResult:
        try:
            img_bytes, mime_type = self._optimize_image(image)
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            if prev_answer and prev_confidence > 0:
                context = GEMINI_CONTEXT_TEMPLATE.format(
                    prev_answer=prev_answer, prev_confidence=prev_confidence)
            else:
                context = GEMINI_CONTEXT_EMPTY
            prompt = GEMINI_PROMPT.format(context=context)

            payload = json.dumps({
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": img_b64}},
                    ]
                }],
                "generationConfig": {
                    "maxOutputTokens": 30,
                    "temperature": 0.0,
                },
            }).encode()

            path = (f"/v1beta/models/{GEMINI_MODEL}:generateContent"
                    f"?key={self._api_key}")
            headers = {"Content-Type": "application/json"}

            # Keep-Alive 接続でリクエスト（切れてたら再接続）
            conn = self._get_conn()
            for attempt in range(2):
                try:
                    conn.request("POST", path, body=payload, headers=headers)
                    resp = conn.getresponse()
                    data = resp.read()
                    if resp.status != 200:
                        return AIResult(error=f"HTTP {resp.status}: {data.decode()[:200]}")
                    break
                except Exception:
                    if attempt == 0:
                        conn.close()
                        conn = http.client.HTTPSConnection(
                            self._GEMINI_HOST, timeout=GEMINI_TIMEOUT)
                        self._local.conn = conn
                    else:
                        raise

            body = json.loads(data)
            text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
            answer, confidence = self._parse_response(text)
            print(f"[DEBUG] Gemini raw: {text!r}")
            return AIResult(answer=answer, confidence=confidence)

        except Exception as e:
            return AIResult(error=str(e))


# === 非同期ラッパー（並列対応） ===

class AsyncAIRunner:
    """AI 推論をバックグラウンドスレッドで並列実行。

    max_concurrent 本のリクエストを同時に飛ばし、
    結果は送信順のタイムスタンプ付きで Queue に返す。
    古い結果は自動的に捨てる。
    """

    def __init__(self, max_concurrent: int = 5):
        self._queue: Queue[tuple[float, AIResult]] = Queue()  # (timestamp, result)
        self._in_flight = 0
        self._lock = threading.Lock()
        self._max_concurrent = max_concurrent
        self._latest_displayed_ts = 0.0  # 最後に表示した結果のタイムスタンプ

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._in_flight >= self._max_concurrent

    @property
    def in_flight(self) -> int:
        with self._lock:
            return self._in_flight

    def submit_image(self, engine, image: Image.Image,
                     prev_answer: str = "", prev_confidence: int = 0,
                     capture_time: float = 0.0,
                     image_name: str = "") -> bool:
        """Gemini 用: 画像を非同期送信。空きスロットがあれば送信して True を返す。"""
        from datetime import datetime
        with self._lock:
            if self._in_flight >= self._max_concurrent:
                return False
            self._in_flight += 1

        ts = time.time()
        cap_ts = capture_time or ts

        def _fmt(t: float) -> str:
            dt = datetime.fromtimestamp(t)
            return dt.strftime("%H:%M:%S") + f".{dt.microsecond // 10000:02d}"

        def _run():
            result = engine.ask_with_image(image, prev_answer, prev_confidence)
            now = time.time()
            cap_to_send = ts - cap_ts
            api_elapsed = now - ts
            cap_to_result = now - cap_ts
            print(f"[TIMING] {image_name} | "
                  f"キャプチャ: {_fmt(cap_ts)} → 到着: {_fmt(now)} | "
                  f"撮影→送信: {cap_to_send:.2f}秒 / API: {api_elapsed:.2f}秒 / 撮影→到着: {cap_to_result:.2f}秒")
            self._queue.put((ts, result))
            with self._lock:
                self._in_flight -= 1

        threading.Thread(target=_run, daemon=True).start()
        return True

    def poll(self) -> AIResult | None:
        """キューから最新の結果を取り出す（古い結果はスキップ）"""
        latest_result = None
        latest_ts = self._latest_displayed_ts

        # キューに溜まっている結果を全部取り出し、最新のものだけ返す
        while True:
            try:
                ts, result = self._queue.get_nowait()
                if ts > latest_ts:
                    latest_ts = ts
                    latest_result = result
            except Empty:
                break

        if latest_result is not None:
            self._latest_displayed_ts = latest_ts

        return latest_result

    def reset(self):
        """タイムスタンプをリセット（リセットボタン用）"""
        self._latest_displayed_ts = 0.0
