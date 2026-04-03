# Air Guitar

カメラで体の動きをリアルタイム検出し、エアギター演奏をOSC/WebSocketで外部アプリ（VJ、音響等）に送信するシステム。

## 概要

- **YOLO Pose** でカメラ映像から骨格を推定
- 5種類のジェスチャーを検出: ストローク (UP/DOWN, 強弱3段階)、ジャンプ、のけぞり、腕掲げ、ピッチ (HIGH/MID/LOW)
- 検出結果を **OSC** と **WebSocket** でリアルタイム送信
- Web UI で曲管理・演奏ビジュアライズ
- 音源アップロード時に自動で前処理 (音源分離 → コード抽出 → BPM/ビート解析 → バッキングトラック生成)

## 必要なもの

| ツール | 用途 |
|--------|------|
| Python 3.9+ | ランタイム |
| ffmpeg | バッキングトラック生成・音源解析 |
| Vamp plugin (Chordino) | コード抽出 |
| Webカメラ | ポーズ検出 (演奏モード) |

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd air-guitar
```

### 2. Python 仮想環境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. ffmpeg のインストール

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 5. Vamp plugin (Chordino) のインストール

コード抽出に必要。

**macOS:**

1. https://code.soundsoftware.ac.uk/projects/nnls-chroma/files から `nnls-chroma` をダウンロード
2. `.dylib` ファイルを `~/Library/Audio/Plug-Ins/Vamp/` に配置

```bash
mkdir -p ~/Library/Audio/Plug-Ins/Vamp
# ダウンロードした .dylib をコピー
cp nnls-chroma-1.1/nnls-chroma.dylib ~/Library/Audio/Plug-Ins/Vamp/
```

**Linux:**

```bash
mkdir -p ~/vamp
# ダウンロードした .so をコピー
cp nnls-chroma.so ~/vamp/
export VAMP_PATH=~/vamp
```

### 6. YOLO モデルの取得

初回実行時に自動ダウンロードされるが、事前に取得する場合:

```bash
python -c "from ultralytics import YOLO; YOLO('yolo11n-pose.pt')"
```

## 起動

### 通常モード (カメラ + Web UI)

```bash
python main.py
```

### Prep のみモード (カメラなし、曲の前処理だけ)

```bash
python main.py --no-camera
```

### オプション

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--http-port` | 3000 | HTTP サーバーポート |
| `--ws-port` | 8765 | WebSocket ポート |
| `--osc-ip` | 127.0.0.1 | OSC 送信先 IP |
| `--osc-port` | 8000 | OSC 送信先ポート |
| `--camera` | 0 | カメラデバイス番号 |
| `--no-camera` | false | カメラなしモード |

起動後 http://localhost:3000 でWeb UIにアクセス。

## 使い方

### 1. 曲の準備

Web UI で音源ファイル (.mp3/.wav) をアップロードすると自動的に前処理が走る:

1. **音源分離** — Demucs (htdemucs_6s) で6ステム分離
2. **コード抽出** — Chordino でコード進行をJSON化
3. **バッキングトラック生成** — ギター以外のステムをミックス
4. **BPM/ビート解析** — librosa でビート位置を検出

### 2. 演奏

曲を選択して Play → カメラの前でエアギター演奏。ジェスチャーがリアルタイムでOSC送信される。

## OSC メッセージ

| アドレス | 引数 | トリガー |
|----------|------|----------|
| `/strum` | direction, intensity | ストローク検出時 |
| `/jump` | (なし) | ジャンプ検出時 |
| `/lean_back` | angle | のけぞり検出時 |
| `/arms_up` | (なし) | 両腕掲げ検出時 |
| `/pitch` | level (HIGH/MID/LOW) | 常時 |
| `/pose` | keypoints JSON | 常時 |

## ファイル構成

```
air-guitar/
  main.py           — 統合エントリポイント (HTTP + WS + カメラ)
  gesture.py         — ジェスチャー検出ロジック
  osc_sender.py      — OSC 送信
  ws_server.py       — WebSocket サーバー
  prep.py            — 前処理パイプライン
  separate.py        — Demucs による音源分離
  extract_chords.py  — Chordino によるコード抽出
  requirements.txt   — Python 依存パッケージ
  web/               — フロントエンド (HTML/CSS/JS)
  songs/             — 曲データ (gitignore)
```
