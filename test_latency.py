#!/usr/bin/env python3
"""端到端レイテンシ計測ツール — リアルタイム時計表示"""

import time
import tkinter as tk
from datetime import datetime


class LatencyTimer:
    def __init__(self):
        self._root = tk.Tk()
        self._root.title("Latency Test")
        self._root.geometry("500x250")
        self._root.configure(bg="#000000")
        self._root.attributes("-topmost", True)

        self._label = tk.Label(
            self._root,
            text="00:00:00.00",
            font=("Menlo", 90, "bold"),
            fg="#00FF00",
            bg="#000000",
        )
        self._label.pack(expand=True, fill="both")

        self._update()
        self._root.mainloop()

    def _update(self):
        now = datetime.now()
        # HH:MM:SS.ss 形式（例: 16:37:45.23）
        text = now.strftime("%H:%M:%S") + f".{now.microsecond // 10000:02d}"
        self._label.config(text=text)
        self._root.after(10, self._update)


if __name__ == "__main__":
    LatencyTimer()
