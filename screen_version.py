#!/usr/bin/env python3
"""みんはやソルバー（高速版）"""

import sys, os, json, threading, time, ssl, base64
import mss
from PIL import Image
from dotenv import load_dotenv
import urllib.request

# SSL証明書検証を無効化
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return None

def save_config(x, y, w, h):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"x": x, "y": y, "w": w, "h": h}, f)

def ask_with_image(img_path):
    """画像を直接Geminiに送って読み取り＋回答を一度に行う"""
    try:
        with open(img_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')

        data = json.dumps({
            "contents": [{
                "parts": [
                    {"text": "これは早押しクイズの問題文の画像です。問題文を読み取り、答えだけを簡潔に回答してください。漢字の場合は読み方をカッコで付けてください。例: 織田信長（おだのぶなが）\n答え:"},
                    {"inline_data": {"mime_type": "image/png", "data": img_data}}
                ]
            }]
        }).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as res:
            result = json.loads(res.read())
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"\nAPI Error: {error_body}")
        return "API Error"
    except Exception as e:
        return str(e)

class Solver:
    def __init__(self):
        self.answer = ""
        self.last_img = None
        self.busy = False
        self.last_call = 0
        self.min_interval = 3  # 最低3秒間隔

    def images_similar(self, img1, img2, threshold=0.95):
        """2つの画像が似ているかチェック（95%以上一致で同じとみなす）"""
        if img1 is None or img2 is None:
            return False
        if img1.size != img2.size:
            return False
        # 縮小して比較（高速化）
        small1 = img1.resize((32, 32)).convert('L')
        small2 = img2.resize((32, 32)).convert('L')
        pixels1 = list(small1.getdata())
        pixels2 = list(small2.getdata())
        matches = sum(abs(p1-p2) < 30 for p1, p2 in zip(pixels1, pixels2))
        return matches / len(pixels1) > threshold

    def process(self, img_path, img):
        if self.busy:
            return

        # 最低間隔チェック
        now = time.time()
        if now - self.last_call < self.min_interval:
            return

        # 画像が大きく変わった時だけAPI呼び出し
        if self.images_similar(img, self.last_img):
            return

        self.last_img = img.copy()
        self.last_call = now
        self.busy = True

        def f():
            result = ask_with_image(img_path)
            if result and "API Error" not in result:
                self.answer = result
            self.busy = False
        threading.Thread(target=f, daemon=True).start()

    def run(self, x, y, w, h):
        img_path = os.path.join(os.path.dirname(__file__), 'capture.png')

        # ターミナルサイズ取得
        try:
            cols = os.get_terminal_size().columns
        except:
            cols = 60

        # 画面クリア＆カーソル非表示
        print("\033[2J\033[H\033[?25l", end="")

        with mss.mss() as sct:
            try:
                while True:
                    shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
                    img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
                    img.save(img_path)

                    self.process(img_path, img)

                    ans = self.answer if self.answer else "(解析中...)"

                    # 画面全体をクリアして中央に大きく表示
                    print("\033[H\033[2J", end="")  # 画面クリア＆ホームへ
                    print(f"\033[42;30m ★回答: {ans[:cols-12]} \033[0m")
                    sys.stdout.flush()

                    time.sleep(0.3)
            except KeyboardInterrupt:
                print("\033[?25h\033[0m\n終了")  # カーソル復元

# メイン
if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("APIキーなし")
        sys.exit(1)

    config = load_config()
    if config:
        x, y, w, h = config['x'], config['y'], config['w'], config['h']
    else:
        print("座標入力:")
        x = int(input("左上X: "))
        y = int(input("左上Y: "))
        w = int(input("幅: "))
        h = int(input("高さ: "))
        save_config(x, y, w, h)

    Solver().run(x, y, w, h)
