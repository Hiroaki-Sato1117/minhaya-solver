# みんはやソルバー v2.0

「みんはや」（みんなで早押しクイズ）の問題文をリアルタイムでキャプチャし、AIが即座に回答を推測する早押しクイズ支援ツール。

## 特徴

- **Gemini 2.5 Flash** による高速画像認識 + 回答推測
- **早押し予測戦略**: 問題文の途中から全体を予測し、累積コンテキストで精度を更新
- **適応的API呼び出し**: 確信度が低い間は高頻度で更新、確定後は節約
- **確信度表示**: AIの回答確信度を 0〜100% でリアルタイム表示
- **2ウィンドウ構成**:
  - 透明キャプチャオーバーレイ（ドラッグ移動・8方向リサイズ対応）
  - 回答表示ウィンドウ（回答 + 確信度バー + 操作ボタン）

## セットアップ

### 必要環境

- macOS
- Python 3.10+

### インストール

```bash
cd ~/Documents/AppDevelop/minhaya-solver
pip3 install -r requirements.txt
```

### APIキーの設定

`.env.example` をコピーして `.env` を作成し、Gemini API キーを設定：

```bash
cp .env.example .env
```

```
GEMINI_API_KEY=your_gemini_api_key_here
```

Gemini API キーは [Google AI Studio](https://aistudio.google.com/apikey) から取得できます。

## 起動方法

```bash
cd ~/Documents/AppDevelop/minhaya-solver
python3 main.py
```

## 使い方

1. 起動すると **キャプチャウィンドウ**（緑枠）と **回答ウィンドウ** が表示される
2. キャプチャウィンドウをみんはやの問題文の上に配置する
   - 枠の辺・四隅をドラッグでリサイズ
   - 中央をドラッグで移動
3. 回答ウィンドウの **「開始」** ボタンを押す
4. 問題文が表示されると、AIが自動で回答を推測して表示する
5. 問題が変わったら **「リセット」** で状態をクリア

### キーボードショートカット

| ショートカット | 動作 |
|---|---|
| `Cmd+Shift+S` | 開始 / 停止 |
| `Cmd+Shift+R` | リセット |

## プロジェクト構成

```
minhaya-solver/
├── main.py              # メインオーケストレーター
├── config.py            # 設定管理（JSON永続化）
├── constants.py         # 定数・プロンプト定義
├── requirements.txt
├── .env / .env.example
├── core/
│   ├── ai_engine.py     # Gemini Vision API + 非同期ラッパー
│   ├── screen_capture.py # mss スクリーンキャプチャ
│   ├── image_diff.py    # 画像変化検出
│   ├── ocr_engine.py    # OCR（未使用・予備）
│   └── text_diff.py     # テキスト類似度
├── ui/
│   ├── answer_window.py # 回答表示ウィンドウ
│   ├── capture_window.py # 透明キャプチャオーバーレイ
│   ├── settings_dialog.py # 設定ダイアログ
│   └── styles.py        # カラー・フォント定義
└── legacy/              # 旧バージョン
```

## 技術構成

- **GUI**: CustomTkinter（ダークテーマ）
- **AI**: Google Gemini 2.5 Flash（thinking無効化で高速応答）
- **キャプチャ**: mss（高速スクリーンキャプチャ）
- **画像最適化**: JPEG圧縮 + リサイズで転送高速化
