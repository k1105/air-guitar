"""Air Guitar Production — 統合エントリポイント

HTTP(静的+API) + WebSocket + カメラ/YOLOを1プロセスで提供。
"""

import argparse
import io
import json
import os
import re
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

import cv2
import numpy as np
from ultralytics import YOLO

from gesture import GestureDetector
from osc_sender import OSCSender
from ws_server import WebSocketServer
from prep import run_prep

BASE_DIR = Path(__file__).parent
SONGS_DIR = BASE_DIR / "songs"
WEB_DIR = BASE_DIR / "web"


# ============================================================
# HTTP Server — 静的ファイル + REST API
# ============================================================

class APIHandler(SimpleHTTPRequestHandler):
    """静的ファイル配信 + /api/* のREST API"""

    def __init__(self, *args, ws_server=None, **kwargs):
        self.ws_server = ws_server
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # API: 曲一覧
        if path == "/api/songs":
            self._respond_json(self._list_songs())
            return

        # API: 曲のファイル取得
        m = re.match(r"^/api/songs/([^/]+)/(.+)$", path)
        if m:
            song_name, filename = m.group(1), m.group(2)
            self._serve_song_file(song_name, filename)
            return

        # 静的ファイル
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/prep":
            self._handle_prep()
            return

        self.send_error(404)

    def _handle_prep(self):
        """音源アップロード→前処理パイプライン"""
        content_type = self.headers.get("Content-Type", "")

        # multipart/form-data パース
        if "multipart/form-data" not in content_type:
            self._respond_json({"error": "multipart/form-data required"}, 400)
            return

        # boundary取得
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip('"')
        if not boundary:
            self._respond_json({"error": "boundary not found"}, 400)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # ファイルを抽出
        filename, file_data = self._parse_multipart(body, boundary)
        if not filename or not file_data:
            self._respond_json({"error": "no file uploaded"}, 400)
            return

        # 一時ファイルに保存
        SONGS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SONGS_DIR / filename
        with open(temp_path, "wb") as f:
            f.write(file_data)

        # 即レスポンス返す（処理はバックグラウンド）
        self._respond_json({"status": "processing", "song": Path(filename).stem})

        # バックグラウンドで前処理実行
        ws = self.ws_server
        def run_in_background():
            try:
                def progress_cb(stage, progress):
                    ws.send_prep_progress(stage, progress)

                run_prep(str(temp_path), str(SONGS_DIR), progress_callback=progress_cb)
                ws.send_prep_done(Path(filename).stem)
            except Exception as e:
                print(f"[ERROR] Prep failed: {e}")
                ws.send_prep_progress("error", 0)
            finally:
                # 一時ファイル削除（songs/<name>/original.* にコピー済み）
                if temp_path.exists() and temp_path.parent == SONGS_DIR:
                    temp_path.unlink(missing_ok=True)

        threading.Thread(target=run_in_background, daemon=True).start()

    def _parse_multipart(self, body, boundary):
        """シンプルなmultipart/form-dataパーサー"""
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)

        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers = part[:header_end].decode("utf-8", errors="replace")
            data = part[header_end + 4:]
            # 末尾の\r\nを除去
            if data.endswith(b"\r\n"):
                data = data[:-2]

            # filenameを取得
            fn_match = re.search(r'filename="([^"]+)"', headers)
            if fn_match:
                return fn_match.group(1), data

        return None, None

    def _list_songs(self):
        """準備済み曲一覧を返す"""
        songs = []
        if SONGS_DIR.exists():
            for d in sorted(SONGS_DIR.iterdir()):
                meta_path = d / "meta.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        songs.append(json.load(f))
        return songs

    def _serve_song_file(self, song_name, filename):
        """songs/<name>/のファイルを配信"""
        file_path = SONGS_DIR / song_name / filename
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return

        # MIMEタイプ推定
        ext = file_path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".json": "application/json",
        }
        content_type = mime_map.get(ext, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def _respond_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # API以外のログを抑制
        if "/api/" in str(args[0]) if args else False:
            super().log_message(format, *args)


def make_handler(ws_server):
    """ws_serverをバインドしたハンドラクラスを返す"""
    class BoundHandler(APIHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, ws_server=ws_server, **kwargs)
    return BoundHandler


# ============================================================
# カメラ + YOLO ループ（演奏モード）
# ============================================================

def camera_loop(model, detector, osc, ws, camera_id=0):
    """カメラキャプチャ → YOLO → ジェスチャー検出 → 送信"""
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print("[ERROR] カメラを開けませんでした")
        return

    print("[INFO] カメラ起動完了")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            frame_h, frame_w = frame.shape[:2]

            results = model(frame, verbose=False)

            keypoints = None
            if results and results[0].keypoints is not None:
                kps = results[0].keypoints
                if kps.data.shape[0] > 0:
                    confs = kps.conf
                    if confs is not None and len(confs) > 0:
                        best_idx = confs.mean(dim=1).argmax().item()
                    else:
                        best_idx = 0
                    keypoints = kps.data[best_idx].cpu().numpy()

            cues = detector.detect(keypoints, frame_h, frame_w)

            if cues:
                osc.send(cues, keypoints)
                ws.send_gesture(cues, keypoints)

                ts = time.strftime("%H:%M:%S")
                for cue in cues:
                    if cue["type"] != "PITCH":
                        print(f"[{ts}] {cue['label']}")
            else:
                ws.send_gesture([], keypoints)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


# ============================================================
# Entry Point
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Air Guitar Production")
    parser.add_argument("--http-port", type=int, default=3000, help="HTTPサーバーポート")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocketポート")
    parser.add_argument("--osc-ip", default="127.0.0.1", help="OSC送信先IP")
    parser.add_argument("--osc-port", type=int, default=8000, help="OSC送信先ポート")
    parser.add_argument("--camera", type=int, default=0, help="カメラデバイス番号")
    parser.add_argument("--no-camera", action="store_true", help="カメラなし（Prepのみ）")
    return parser.parse_args()


def main():
    args = parse_args()

    SONGS_DIR.mkdir(parents=True, exist_ok=True)

    # WebSocket起動
    ws = WebSocketServer(port=args.ws_port)
    ws.start()

    # HTTPサーバー起動
    handler_class = make_handler(ws)
    httpd = HTTPServer(("0.0.0.0", args.http_port), handler_class)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    print(f"[HTTP] http://localhost:{args.http_port}")

    if args.no_camera:
        print("[INFO] カメラなしモード（Prepのみ）")
        print("[INFO] Ctrl+C で終了")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[INFO] 終了")
        return

    # YOLO + ジェスチャー検出
    print("[INFO] YOLOモデル読み込み中...")
    model = YOLO("yolo11n-pose.pt")
    detector = GestureDetector(fps=30)
    osc = OSCSender(ip=args.osc_ip, port=args.osc_port)

    print(f"[OSC] → {args.osc_ip}:{args.osc_port}")
    print("[INFO] Ctrl+C で終了")

    camera_loop(model, detector, osc, ws, camera_id=args.camera)


if __name__ == "__main__":
    main()
