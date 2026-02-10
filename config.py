"""設定管理 (JSON永続化)"""

import json
import os
from constants import (
    CONFIG_FILE,
    CAPTURE_DEFAULT_X, CAPTURE_DEFAULT_Y,
    CAPTURE_DEFAULT_W, CAPTURE_DEFAULT_H,
    ANSWER_DEFAULT_X, ANSWER_DEFAULT_Y,
    ANSWER_DEFAULT_W, ANSWER_DEFAULT_H,
    MIN_API_INTERVAL_SEC, CAPTURE_INTERVAL_MS,
)

_DEFAULTS = {
    "capture": {
        "x": CAPTURE_DEFAULT_X,
        "y": CAPTURE_DEFAULT_Y,
        "w": CAPTURE_DEFAULT_W,
        "h": CAPTURE_DEFAULT_H,
    },
    "answer_window": {
        "x": ANSWER_DEFAULT_X,
        "y": ANSWER_DEFAULT_Y,
        "w": ANSWER_DEFAULT_W,
        "h": ANSWER_DEFAULT_H,
    },
    "engine": "gemini",            # "gemini" | "claude"
    "api_interval": MIN_API_INTERVAL_SEC,
    "capture_interval_ms": CAPTURE_INTERVAL_MS,
    "auto_start": False,
}


class ConfigStore:
    """JSON ベースの設定管理。変更は即座にファイルへ書き出す。"""

    def __init__(self, path: str = CONFIG_FILE):
        self._path = path
        self._data: dict = {}
        self._load()

    # --- public API ---

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def get_capture_rect(self) -> dict:
        return dict(self._data.get("capture", _DEFAULTS["capture"]))

    def set_capture_rect(self, x: int, y: int, w: int, h: int):
        self._data["capture"] = {"x": x, "y": y, "w": w, "h": h}
        self._save()

    def get_answer_window_rect(self) -> dict:
        return dict(self._data.get("answer_window", _DEFAULTS["answer_window"]))

    def set_answer_window_rect(self, x: int, y: int, w: int, h: int):
        self._data["answer_window"] = {"x": x, "y": y, "w": w, "h": h}
        self._save()

    @property
    def engine(self) -> str:
        return self._data.get("engine", _DEFAULTS["engine"])

    @engine.setter
    def engine(self, value: str):
        self._data["engine"] = value
        self._save()

    @property
    def api_interval(self) -> float:
        return self._data.get("api_interval", _DEFAULTS["api_interval"])

    @property
    def capture_interval_ms(self) -> int:
        return self._data.get("capture_interval_ms", _DEFAULTS["capture_interval_ms"])

    # --- internal ---

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    raw = json.load(f)
            except (json.JSONDecodeError, OSError):
                raw = {}
            self._data = self._migrate(raw)
        else:
            self._data = dict(_DEFAULTS)
            self._save()

    def _migrate(self, raw: dict) -> dict:
        """旧フォーマット {"x","y","w","h"} → 新フォーマットへ変換
        また、古い小さいデフォルト値を補正する。
        """
        if "capture" in raw:
            # 既に v2 形式
            merged = dict(_DEFAULTS)
            merged.update(raw)
            # 旧デフォルト高さ (340) で保存されていたら補正
            aw = merged.get("answer_window", {})
            if aw.get("h", 0) < 400:
                aw["h"] = ANSWER_DEFAULT_H
                merged["answer_window"] = aw
            return merged

        # 旧フォーマット: トップレベルに x/y/w/h がある
        if "x" in raw and "y" in raw:
            migrated = dict(_DEFAULTS)
            migrated["capture"] = {
                "x": raw["x"], "y": raw["y"],
                "w": raw["w"], "h": raw["h"],
            }
            self._save_data(migrated)
            return migrated

        merged = dict(_DEFAULTS)
        merged.update(raw)
        return merged

    def _save(self):
        self._save_data(self._data)

    def _save_data(self, data: dict):
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass
