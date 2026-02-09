"""定数・デフォルト値定義"""

import os

# --- パス ---
CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")
LEGACY_CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# --- タイミング ---
CAPTURE_INTERVAL_MS = 300          # キャプチャ間隔 (ms)
MIN_API_INTERVAL_SEC = 3.0         # API 最低呼び出し間隔 (秒)
IMAGE_DIFF_THRESHOLD = 0.95        # 画像一致率しきい値
TEXT_SIMILARITY_THRESHOLD = 0.80   # テキスト類似度しきい値
OCR_MIN_TEXT_LENGTH = 3            # OCR 最低文字数

# --- AI モデル ---
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 50
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_TIMEOUT = 10

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
ANSWER_DEFAULT_H = 340

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
    "これは早押しクイズの問題文の画像です。問題文を読み取り、答えだけを簡潔に回答してください。"
    "漢字の場合は読み方をカッコで付けてください。例: 織田信長（おだのぶなが）\n答え:"
)
