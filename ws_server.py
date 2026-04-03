"""WebSocketサーバー — ジェスチャー送信 + prep進捗通知"""

import asyncio
import json
import time
import threading
from websockets.asyncio.server import serve


class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self._loop = None
        self._thread = None

    async def _handler(self, websocket):
        self.clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        finally:
            self.clients.discard(websocket)

    async def _broadcast(self, message):
        if not self.clients:
            return
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(message)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    def _schedule_broadcast(self, data):
        """メインスレッドからブロードキャスト"""
        if self._loop is None or not self.clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self._loop)

    def send_gesture(self, cues, keypoints=None):
        """ジェスチャー検出結果を送信（拡張フォーマット）"""
        msg = {
            "type": "gesture",
            "timestamp": time.time(),
            "cues": [c["label"] for c in cues],
            "cue_types": [c["type"] for c in cues],
        }

        # 構造化フィールド抽出
        for cue in cues:
            if cue["type"] == "STRUM":
                msg["strum_detail"] = {
                    "direction": cue["direction"],
                    "intensity": cue["intensity"],
                }
            elif cue["type"] == "PITCH":
                msg["pitch_level"] = cue["level"]

        if keypoints is not None:
            msg["keypoints"] = keypoints.tolist()

        self._schedule_broadcast(json.dumps(msg))

    def send_prep_progress(self, stage, progress):
        """前処理進捗を送信"""
        msg = json.dumps({
            "type": "prep_progress",
            "stage": stage,
            "progress": progress,
        })
        self._schedule_broadcast(msg)

    def send_prep_done(self, song_name):
        """前処理完了通知"""
        msg = json.dumps({
            "type": "prep_done",
            "song": song_name,
        })
        self._schedule_broadcast(msg)

    def start(self):
        """別スレッドでWebSocketサーバーを起動"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    async def _serve(self):
        async with serve(self._handler, self.host, self.port) as server:
            print(f"[WS] WebSocket server running on ws://{self.host}:{self.port}")
            await asyncio.get_running_loop().create_future()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())
