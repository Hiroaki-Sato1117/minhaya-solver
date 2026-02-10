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
    GEMINI_CONTEXT_TEMPLATE, GEMINI_CONTEXT_EMPTY,
    IMAGE_MAX_WIDTH, IMAGE_JPEG_QUALITY,
)

# Gemini 用に SSL 検証を緩和
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

    def __init__(self, api_key: str):
        self._api_key = api_key

    @staticmethod
    def _optimize_image(image: Image.Image) -> tuple[bytes, str]:
        """画像をリサイズ+JPEG圧縮して転送サイズを削減"""
        img = image
        # リサイズ（幅が大きすぎる場合）
        if img.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / img.width
            new_h = int(img.height * ratio)
            img = img.resize((IMAGE_MAX_WIDTH, new_h), Image.LANCZOS)

        # JPEG 圧縮（PNG の 1/5〜1/10 のサイズ）
        buf = io.BytesIO()
        rgb = img.convert("RGB") if img.mode != "RGB" else img
        rgb.save(buf, format="JPEG", quality=IMAGE_JPEG_QUALITY)
        return buf.getvalue(), "image/jpeg"

    @staticmethod
    def _parse_response(text: str) -> tuple[str, float]:
        """Gemini レスポンスから回答と確信度をパース"""
        import re
        confidence = 0.0

        # 確信度を抽出
        conf_match = re.search(r'確信度\s*[:：]\s*(\d+)', text)
        if conf_match:
            confidence = min(100, max(0, int(conf_match.group(1)))) / 100.0

        # 答えを抽出
        answer = "不明"
        ans_match = re.search(r'答え\s*[:：]\s*(.+)', text)
        if ans_match:
            raw = ans_match.group(1).strip()
            raw = re.split(r'\n|確信度', raw)[0].strip()
            # 長すぎる回答（20文字超）は説明文と判断して不明にする
            if len(raw) <= 30 and raw:
                answer = raw
            else:
                answer = "不明"
                confidence = 0.0
        else:
            # 形式に従っていない → 不明
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

            # 前回の推測があればコンテキストに含める
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
                    "maxOutputTokens": 60,
                    "temperature": 0.0,
                    "thinkingConfig": {
                        "thinkingBudget": 0,
                    },
                },
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
                answer, confidence = self._parse_response(text)
                print(f"[DEBUG] Gemini raw: {text!r}")
                return AIResult(answer=answer, confidence=confidence)

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

    def submit_image(self, engine: GeminiVisionEngine, image: Image.Image,
                     prev_answer: str = "", prev_confidence: int = 0):
        """Gemini 用: 画像を非同期送信（前回の推測コンテキスト付き）"""
        if self._busy:
            return
        self._busy = True

        def _run():
            result = engine.ask_with_image(image, prev_answer, prev_confidence)
            self._queue.put(result)
            self._busy = False

        threading.Thread(target=_run, daemon=True).start()

    def poll(self) -> AIResult | None:
        """キューから結果を取り出す（ノンブロッキング）"""
        try:
            return self._queue.get_nowait()
        except Empty:
            return None
