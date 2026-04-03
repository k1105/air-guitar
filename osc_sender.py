"""OSC送信モジュール"""

import json
from pythonosc import udp_client


class OSCSender:
    def __init__(self, ip="127.0.0.1", port=8000):
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.ip = ip
        self.port = port

    def send(self, cues, keypoints=None):
        """検出されたキューをOSCで送信する"""
        for cue in cues:
            cue_type = cue["type"]

            if cue_type == "STRUM":
                self.client.send_message("/strum", [cue["direction"], cue["intensity"]])
            elif cue_type == "JUMP":
                self.client.send_message("/jump", [])
            elif cue_type == "LEAN_BACK":
                self.client.send_message("/lean_back", [cue["angle"]])
            elif cue_type == "ARMS_UP":
                self.client.send_message("/arms_up", [])
            elif cue_type == "PITCH":
                self.client.send_message("/pitch", [cue["level"]])

        # デバッグ用: 全キーポイント座標をJSON送信
        if keypoints is not None:
            self.client.send_message("/pose", [json.dumps(keypoints.tolist())])
