"""OCR エンジン（Apple Vision / Null）"""

from __future__ import annotations
import io
from PIL import Image


class NullOCR:
    """OCR を使わないダミー実装 (Gemini Vision モード用)"""
    def recognize(self, image: Image.Image) -> str:
        return ""


class AppleVisionOCR:
    """macOS Apple Vision Framework による高速 OCR"""

    def __init__(self):
        # 遅延 import — macOS 以外では ImportError
        import Vision as _Vision          # noqa: F811
        import Quartz as _Quartz          # noqa: F811
        from Foundation import NSData as _NSData  # noqa: F811
        self._Vision = _Vision
        self._Quartz = _Quartz
        self._NSData = _NSData

    def recognize(self, image: Image.Image) -> str:
        """PIL Image → テキスト"""
        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            ns_data = self._NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))

            provider = self._Quartz.CGDataProviderCreateWithCFData(ns_data)
            cg_image = self._Quartz.CGImageCreateWithPNGDataProvider(
                provider, None, True, self._Quartz.kCGRenderingIntentDefault,
            )
            if cg_image is None:
                return ""

            request = self._Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(self._Vision.VNRequestTextRecognitionLevelAccurate)
            request.setRecognitionLanguages_(["ja", "en"])
            request.setUsesLanguageCorrection_(True)

            handler = self._Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None,
            )
            success = handler.performRequests_error_([request], None)
            if not success:
                return ""

            results = request.results()
            if not results:
                return ""

            texts = [obs.topCandidates_(1)[0].string() for obs in results]
            return "\n".join(texts)

        except Exception as e:
            print(f"[OCR Error] {e}")
            return ""


def create_ocr(name: str = "apple_vision") -> NullOCR | AppleVisionOCR:
    """名前から OCR エンジンを生成"""
    if name == "apple_vision":
        try:
            return AppleVisionOCR()
        except ImportError:
            print("[OCR] Apple Vision が利用できません。NullOCR を使用します。")
            return NullOCR()
    return NullOCR()
