"""定数・デフォルト値定義"""

import os

# --- パス ---
CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")
LEGACY_CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# --- タイミング ---
CAPTURE_INTERVAL_MS = 150          # キャプチャ間隔 (ms)
MIN_API_INTERVAL_SEC = 0.5         # API 最低呼び出し間隔 (秒)
IMAGE_DIFF_THRESHOLD = 0.95        # 画像一致率しきい値
TEXT_SIMILARITY_THRESHOLD = 0.80   # テキスト類似度しきい値
OCR_MIN_TEXT_LENGTH = 3            # OCR 最低文字数

# --- AI モデル ---
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 50
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TIMEOUT = 15

# --- キャプチャウィンドウ デフォルト ---
CAPTURE_DEFAULT_X = 100
CAPTURE_DEFAULT_Y = 100
CAPTURE_DEFAULT_W = 400
CAPTURE_DEFAULT_H = 200
CAPTURE_MIN_W = 80
CAPTURE_MIN_H = 40
CAPTURE_BORDER_WIDTH = 3
RESIZE_HANDLE_SIZE = 12

# --- 回答ウィンドウ デフォルト ---
ANSWER_DEFAULT_X = 100
ANSWER_DEFAULT_Y = 400
ANSWER_DEFAULT_W = 520
ANSWER_DEFAULT_H = 440

# --- カラー (hex) ---
MINHAYA_PURPLE = "#6C3FB5"
MINHAYA_PURPLE_DARK = "#5A2FA0"
MINHAYA_PURPLE_LIGHT = "#8B6FCF"
MINHAYA_GOLD = "#FFD700"
MINHAYA_BG = "#1A1035"
MINHAYA_BG_CARD = "#2A1F4E"
MINHAYA_TEXT = "#FFFFFF"
MINHAYA_TEXT_DIM = "#A0A0B0"
MINHAYA_GREEN = "#4CAF50"
MINHAYA_RED = "#F44336"
MINHAYA_ORANGE = "#FF9800"
CAPTURE_BORDER_COLOR = "#00FF00"
CAPTURE_BORDER_ACTIVE = "#FFD700"

# --- フォント ---
FONT_FAMILY = "Hiragino Sans"
FONT_PATHS = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

# --- AI プロンプト ---
CLAUDE_PROMPT_TEMPLATE = """早押しクイズです。問題文の途中かもしれませんが、推測して答えを1つだけ簡潔に答えてください。

問題: {question}

答え（単語のみ）:"""

GEMINI_PROMPT = (
    "早押しクイズ。画像の問題文から答えを推測せよ。\n"
    "【絶対ルール】\n"
    "・答えの単語だけを返せ。説明・描写・文章は一切禁止。\n"
    "・分からなければ「不明」とだけ返せ。\n"
    "・漢字には読みをカッコで付けろ。\n"
    "{context}"
    "形式（厳守・2行のみ）:\n"
    "答え:単語（よみがな）\n"
    "確信度:0-100"
)

# 前回の推測を含めるテンプレート
GEMINI_CONTEXT_TEMPLATE = "前回の推測: {prev_answer}（確信度{prev_confidence}%）。問題文が更新された。推測を維持or修正せよ。\n"
GEMINI_CONTEXT_EMPTY = ""

# 画像最適化
IMAGE_MAX_WIDTH = 640              # API送信前の最大幅 (px)
IMAGE_JPEG_QUALITY = 70            # JPEG圧縮品質（速度優先）
