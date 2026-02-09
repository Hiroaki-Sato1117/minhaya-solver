"""AI 推論エンジン（Claude / Gemini Vision）"""

from __future__ import annotations
import base64
import io
import json
import ssl
import threading
import urllib.request
from queue import Queue, Empty
from typing import Callable

from PIL import Image

from constants import (
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_PROMPT_TEMPLATE,
    GEMINI_MODEL, GEMINI_TIMEOUT, GEMINI_PROMPT,
)

# Gemini 用に SSL 検証を緩和
ssl._create_default_https_context = ssl._create_unverified_context


# === 結果オブジェクト ===

class AIResult:
    __slots__ = ("answer", "error")
    def __init__(self, answer: str = "", error: str = ""):
        self.answer = answer
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

    def __init__(self, api_key: str):
        self._api_key = api_key

    def ask_with_image(self, image: Image.Image) -> AIResult:
        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            payload = json.dumps({
                "contents": [{
                    "parts": [
                        {"text": GEMINI_PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                    ]
                }]
            }).encode()

            url = (
                f"https://generativelanguage.googleapis.com/v1beta/"
                f"models/{GEMINI_MODEL}:generateContent?key={self._api_key}"
            )
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as res:
                body = json.loads(res.read())
                text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
                return AIResult(answer=text)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            return AIResult(error=f"HTTP {e.code}: {error_body}")
        except Exception as e:
            return AIResult(error=str(e))


# === 非同期ラッパー ===

class AsyncAIRunner:
    """AI 推論をバックグラウンドスレッドで実行し、結果を Queue に返す。

    メインスレッド側は `poll()` で結果を取り出す。
    """

    def __init__(self):
        self._queue: Queue[AIResult] = Queue()
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def submit_text(self, engine: ClaudeEngine, question: str):
        """Claude 用: テキスト質問を非同期送信"""
        if self._busy:
            return
        self._busy = True

        def _run():
            result = engine.ask(question)
            self._queue.put(result)
            self._busy = False

        threading.Thread(target=_run, daemon=True).start()

    def submit_image(self, engine: GeminiVisionEngine, image: Image.Image):
        """Gemini 用: 画像を非同期送信"""
        if self._busy:
            return
        self._busy = True

        def _run():
            result = engine.ask_with_image(image)
            self._queue.put(result)
            self._busy = False

        threading.Thread(target=_run, daemon=True).start()

    def poll(self) -> AIResult | None:
        """キューから結果を取り出す（ノンブロッキング）"""
        try:
            return self._queue.get_nowait()
        except Empty:
            return None
