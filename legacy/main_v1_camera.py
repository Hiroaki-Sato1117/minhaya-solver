#!/usr/bin/env python3
"""
みんはや早押しクイズ回答支援ツール
- 起動時にマウスで問題領域を選択
- Apple Vision Frameworkで高速OCR
- 非同期処理でリアルタイム回答
- 問題途中でも推測回答
"""

import cv2
import anthropic
import time
import os
import threading
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import Vision
import Quartz
from Foundation import NSData

load_dotenv()

CAMERA_INDEX = 0

class MinhayaSolver:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.current_answer = "領域を選択してください..."
        self.current_question = ""
        self.last_sent_question = ""
        self.roi = None  # 選択領域 (x, y, w, h)
        self.selecting = False
        self.selection_start = None
        self.selection_end = None
        self.font = self._load_font()
        self.processing = False
        self.lock = threading.Lock()

    def _load_font(self):
        """日本語フォントを読み込み"""
        font_paths = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, 36)
                except:
                    continue
        return ImageFont.load_default()

    def put_japanese_text(self, frame, text, position, color=(0, 255, 0), font_size=36):
        """OpenCVフレームに日本語テキストを描画"""
        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", font_size)
        except:
            font = self.font
        draw.text(position, text, font=font, fill=color)
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def ocr_apple_vision(self, frame):
        """Apple Vision Frameworkで高速OCR"""
        try:
            # OpenCV BGR -> RGB -> PNG
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            # PILイメージをNSDataに変換
            import io
            buffer = io.BytesIO()
            pil_img.save(buffer, format='PNG')
            png_data = buffer.getvalue()
            ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))

            # CGImageを作成
            data_provider = Quartz.CGDataProviderCreateWithCFData(ns_data)
            cg_image = Quartz.CGImageCreateWithPNGDataProvider(
                data_provider, None, True, Quartz.kCGRenderingIntentDefault
            )

            if cg_image is None:
                return ""

            # Vision リクエスト
            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
            request.setRecognitionLanguages_(["ja", "en"])
            request.setUsesLanguageCorrection_(True)

            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
            success = handler.performRequests_error_([request], None)

            if not success:
                return ""

            results = request.results()
            if not results:
                return ""

            # テキスト抽出
            texts = []
            for observation in results:
                text = observation.topCandidates_(1)[0].string()
                texts.append(text)

            return "\n".join(texts)

        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    def get_answer_async(self, question):
        """非同期で回答を取得"""
        if self.processing:
            return

        # 類似度チェック（同じ質問は送らない）
        if self._similar(question, self.last_sent_question):
            return

        self.processing = True
        self.last_sent_question = question

        def fetch():
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=50,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""早押しクイズです。問題文の途中かもしれませんが、推測して答えを1つだけ簡潔に答えてください。

問題: {question}

答え（単語のみ）:"""
                        }
                    ]
                )
                answer = response.content[0].text.strip()
                with self.lock:
                    self.current_answer = answer
                print(f">>> {answer}")
            except Exception as e:
                print(f"API Error: {e}")
            finally:
                self.processing = False

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def _similar(self, s1, s2):
        """2つの文字列が似ているかチェック"""
        if not s1 or not s2:
            return False
        # 80%以上一致したら同じとみなす
        shorter = min(len(s1), len(s2))
        if shorter == 0:
            return False
        common = sum(c1 == c2 for c1, c2 in zip(s1, s2))
        return common / shorter > 0.8

    def mouse_callback(self, event, x, y, flags, param):
        """マウスイベント処理"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.selecting = True
            self.selection_start = (x, y)
            self.selection_end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.selecting:
            self.selection_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.selecting = False
            self.selection_end = (x, y)
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            self.roi = (min(x1, x2), min(y1, y2), abs(x2-x1), abs(y2-y1))
            if self.roi[2] > 10 and self.roi[3] > 10:
                self.current_answer = "認識中..."
                print(f"領域選択: {self.roi}")
            else:
                self.roi = None

    def run(self):
        """メインループ"""
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        if not cap.isOpened():
            print("カメラを開けませんでした")
            return

        window_name = 'Minhaya Solver'
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.mouse_callback)

        print("=== みんはやソルバー ===")
        print("1. マウスで問題領域をドラッグして選択")
        print("2. 'r'キーで領域リセット")
        print("3. 'q'キーで終了")
        print("=" * 30)

        last_ocr_time = 0
        ocr_interval = 0.15  # OCR間隔

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    continue

                display = frame.copy()
                h, w = display.shape[:2]

                # 選択中の領域を表示
                if self.selecting and self.selection_start and self.selection_end:
                    cv2.rectangle(display, self.selection_start, self.selection_end, (0, 255, 0), 2)

                # 選択済み領域を表示
                if self.roi:
                    x, y, rw, rh = self.roi
                    cv2.rectangle(display, (x, y), (x+rw, y+rh), (0, 255, 0), 2)

                    # ROI内をOCR
                    current_time = time.time()
                    if current_time - last_ocr_time >= ocr_interval:
                        last_ocr_time = current_time
                        roi_frame = frame[y:y+rh, x:x+rw]
                        if roi_frame.size > 0:
                            text = self.ocr_apple_vision(roi_frame)
                            if text and len(text) >= 3:
                                self.current_question = text
                                # 非同期で回答取得
                                self.get_answer_async(text)

                # 回答表示エリア
                overlay = display.copy()
                cv2.rectangle(overlay, (0, h-70), (w, h), (0, 0, 0), -1)
                display = cv2.addWeighted(overlay, 0.8, display, 0.2, 0)

                # 回答テキスト
                with self.lock:
                    answer_text = self.current_answer
                display = self.put_japanese_text(display, f"回答: {answer_text}", (10, h-60), (0, 255, 0), 40)

                # 検出テキスト（小さく表示）
                if self.current_question:
                    q_short = self.current_question[:40] + "..." if len(self.current_question) > 40 else self.current_question
                    display = self.put_japanese_text(display, f"検出: {q_short}", (10, 10), (255, 255, 0), 20)

                cv2.imshow(window_name, display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    self.roi = None
                    self.current_answer = "領域を選択してください..."
                    self.current_question = ""
                    print("領域リセット")

        finally:
            cap.release()
            cv2.destroyAllWindows()


def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY が設定されていません")
        return

    solver = MinhayaSolver()
    solver.run()


if __name__ == "__main__":
    main()
