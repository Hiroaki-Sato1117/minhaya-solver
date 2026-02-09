#!/usr/bin/env python3
"""OCRテスト用スクリプト - 保存済み座標を使用"""
import os, json, subprocess
import mss
from PIL import Image

CONFIG_FILE = os.path.expanduser("~/.minhaya_config.json")

# 座標読み込み
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    x, y, w, h = config['x'], config['y'], config['w'], config['h']
    print(f"座標: X={x}, Y={y}, 幅={w}, 高さ={h}")
else:
    print("座標設定がありません。screen_version.pyを先に実行してください。")
    exit(1)

input("Enterでキャプチャ: ")

# キャプチャ
with mss.mss() as sct:
    shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
    img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
    img.save('test_capture.png')
    print(f"画像保存: test_capture.png ({w}x{h})")

# OCR テスト（複数のPSMモードで比較）
print("\n=== OCR結果比較 ===")
for psm in [3, 4, 6, 11]:
    result = subprocess.run(
        ['tesseract', 'test_capture.png', 'stdout', '-l', 'jpn', f'--psm', str(psm), '--oem', '1'],
        capture_output=True
    )
    text = result.stdout.decode('utf-8').strip()
    print(f"\n[PSM {psm}]")
    print(text if text else "(認識なし)")
    print("-" * 40)
