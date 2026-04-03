---
name: setup
description: ゼロからの環境構築をステップバイステップでガイドする。依存関係インストール → venv → Vamp plugin → YOLOモデル → 動作確認まで。 (user)
allowed-tools: Read, Bash, Grep, Glob, Agent, AskUserQuestion
---

# Air Guitar セットアップガイド

完全に1からの環境構築を対話的にガイドするスキル。各ステップで状態を確認しながら進める。

## Instructions

ユーザーの環境を順番にチェックし、不足があれば解決してから次に進む。**各ステップで実際にコマンドを実行して確認し、問題があればその場で対処する。**

### Step 1: 前提ツールの確認

以下を順番にチェック:

```bash
python3 --version   # 3.9以上が必要
ffmpeg -version      # バッキングトラック生成に必要
brew --version       # macOSの場合、パッケージマネージャ
```

不足があれば:
- Python: `brew install python@3.11` (macOS) / `sudo apt install python3` (Linux)
- ffmpeg: `brew install ffmpeg` (macOS) / `sudo apt install ffmpeg` (Linux)

**ユーザーに確認してからインストールを実行すること。**

### Step 2: Python 仮想環境の作成

```bash
cd <project-root>
python3 -m venv venv
source venv/bin/activate
```

すでに `venv/` が存在する場合はスキップ。

### Step 3: Python パッケージのインストール

```bash
source venv/bin/activate
pip install -r requirements.txt
```

主要パッケージ:
- `ultralytics` — YOLO Pose
- `opencv-python` — カメラキャプチャ
- `demucs` — 音源分離
- `librosa` — ビート解析
- `chord-extractor` + `vamp` — コード抽出
- `python-osc` — OSC送信
- `websockets` — WebSocket

インストール失敗時の対処:
- `vamp` が失敗 → Step 4 の Vamp plugin が必要
- macOS で OpenCV が失敗 → `pip install opencv-python-headless` を試す

### Step 4: Vamp Plugin (Chordino) のインストール

コード抽出に必要な Vamp プラグイン。

**macOS の場合:**

1. https://code.soundsoftware.ac.uk/projects/nnls-chroma/files からダウンロード
2. `.dylib` を配置:

```bash
mkdir -p ~/Library/Audio/Plug-Ins/Vamp
# ダウンロードした nnls-chroma.dylib をコピー
```

確認:

```bash
ls ~/Library/Audio/Plug-Ins/Vamp/
# nnls-chroma.dylib が存在すればOK
```

**Linux の場合:**

```bash
mkdir -p ~/vamp
# .so ファイルを ~/vamp/ に配置
export VAMP_PATH=~/vamp  # .bashrc にも追加
```

**このステップはファイルの手動ダウンロードが必要なので、ユーザーにダウンロードリンクを案内し、完了を待つ。**

### Step 5: YOLO モデルの取得

```bash
source venv/bin/activate
python -c "from ultralytics import YOLO; YOLO('yolo11n-pose.pt')"
```

`yolo11n-pose.pt` がプロジェクトルートに生成される。

### Step 6: 動作確認

#### 6a. カメラなしモード (最小確認)

```bash
source venv/bin/activate
python main.py --no-camera
```

期待される出力:
```
[WS] WebSocket server running on ws://0.0.0.0:8765
[HTTP] http://localhost:3000
[INFO] カメラなしモード（Prepのみ）
```

ブラウザで http://localhost:3000 を開いてWeb UIが表示されることを確認。Ctrl+C で終了。

#### 6b. カメラありモード (フル確認)

```bash
python main.py
```

Webカメラが必要。カメラが検出できない場合は `--camera 1` など別のデバイス番号を試す。

### Step 7: 曲の前処理テスト (オプション)

1. `python main.py --no-camera` で起動
2. ブラウザで http://localhost:3000 にアクセス
3. 音源ファイル (.mp3 / .wav) をアップロード
4. 前処理の進捗がリアルタイムで表示される
5. 完了すると曲一覧に表示される

前処理には数分かかる（Demucsの音源分離が重い）。

## 完了条件

- `python main.py --no-camera` が正常起動
- http://localhost:3000 でWeb UIが表示
- (オプション) 音源アップロード→前処理が正常完了

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| `ModuleNotFoundError: vamp` | Vamp plugin未インストール (Step 4) |
| `VAMP_PATH` 関連エラー | `export VAMP_PATH=~/Library/Audio/Plug-Ins/Vamp` を設定 |
| カメラが開けない | `--camera 1` を試す / カメラの権限設定を確認 |
| ffmpeg not found | `brew install ffmpeg` / `apt install ffmpeg` |
| Demucs が遅い | GPUなし環境では正常。初回はモデルDLもあり時間がかかる |
