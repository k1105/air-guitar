"""ジェスチャー判定ロジック — 5種類のエアギターキュー検出"""

import time
import math
import numpy as np


class GestureDetector:
    """YOLO Poseのキーポイントからエアギターのジェスチャーを判定する"""

    # COCO 17点キーポイント番号
    L_SHOULDER, R_SHOULDER = 5, 6
    L_WRIST, R_WRIST = 9, 10
    L_HIP, R_HIP = 11, 12
    L_ANKLE, R_ANKLE = 15, 16

    def __init__(self, fps=30):
        self.fps = fps

        # ストローク用の状態（両手首を独立追跡）
        self.wrist_state = {
            self.L_WRIST: {"prev_y": None, "smoothed_v": 0, "prev_smoothed_v": 0},
            self.R_WRIST: {"prev_y": None, "smoothed_v": 0, "prev_smoothed_v": 0},
        }
        self.last_strum_time = 0
        self.strum_debounce = 0.15  # 150ms（クオンタイズがタイミング補正するので緩め）
        self.velocity_smoothing = 0.4  # EMA係数（0に近いほど滑らか）
        self.strum_armed = True  # ヒステリシス: 速度が落ちるまで再発火しない

        # 速度閾値（px/s）— 1280x720で腕を意図的に振らないと超えない値
        self.strum_velocity_threshold = 800
        self.strum_rearm_threshold = 600  # 再アーム閾値（緩め、素早い連打に対応）

        # 強弱閾値（加速度 px/s^2）
        self.accel_light = 8000
        self.accel_heavy = 20000

        # ジャンプ用の状態
        self.prev_l_ankle_y = None
        self.prev_r_ankle_y = None
        self.last_jump_time = 0
        self.jump_cooldown = 0.5  # 0.5秒

        # のけぞり閾値（度）
        self.lean_back_angle_threshold = 20

    def detect(self, keypoints, frame_h, frame_w):
        """
        全ジェスチャーを判定して結果リストを返す。

        Args:
            keypoints: shape (17, 3) — [x, y, confidence] per keypoint
            frame_h: フレーム高さ
            frame_w: フレーム幅

        Returns:
            list of dict: 検出されたキュー
        """
        cues = []
        now = time.time()

        if keypoints is None or len(keypoints) < 17:
            for s in self.wrist_state.values():
                s["prev_y"] = None
                s["smoothed_v"] = 0
                s["prev_smoothed_v"] = 0
            self.prev_l_ankle_y = None
            self.prev_r_ankle_y = None
            return cues

        kp = np.array(keypoints)

        # 信頼度が低いキーポイントはスキップ用のヘルパー
        def valid(idx):
            return kp[idx][2] > 0.3

        # --- 1. ストローク (STRUM) ---
        strum = self._detect_strum(kp, now, valid)
        if strum:
            cues.append(strum)

        # --- 2. ジャンプ (JUMP) ---
        jump = self._detect_jump(kp, now, frame_h, valid)
        if jump:
            cues.append(jump)

        # --- 3. のけぞり (LEAN BACK) ---
        lean = self._detect_lean_back(kp, valid)
        if lean:
            cues.append(lean)

        # --- 4. 腕掲げ (ARMS UP) ---
        arms = self._detect_arms_up(kp, valid)
        if arms:
            cues.append(arms)

        # --- 5. 左手ピッチ (PITCH) ---
        pitch = self._detect_pitch(kp, frame_h, valid)
        if pitch:
            cues.append(pitch)

        return cues

    def _update_wrist_velocity(self, kp, wrist_idx, valid):
        """手首の速度・加速度を更新して返す。無効なら (None, None)"""
        s = self.wrist_state[wrist_idx]

        if not valid(wrist_idx):
            s["prev_y"] = None
            s["smoothed_v"] = 0
            s["prev_smoothed_v"] = 0
            return None, None

        y = kp[wrist_idx][1]

        if s["prev_y"] is None:
            s["prev_y"] = y
            s["smoothed_v"] = 0
            s["prev_smoothed_v"] = 0
            return None, None

        raw_v = (y - s["prev_y"]) * self.fps
        a = self.velocity_smoothing
        s["smoothed_v"] = a * raw_v + (1 - a) * s["smoothed_v"]
        accel = abs(s["smoothed_v"] - s["prev_smoothed_v"]) * self.fps

        s["prev_y"] = y
        s["prev_smoothed_v"] = s["smoothed_v"]

        return s["smoothed_v"], accel

    def _detect_strum(self, kp, now, valid):
        """両手首のY軸速度でストローク検出。どちらか速い方で判定"""
        # 両手首の速度を更新
        l_vel, l_accel = self._update_wrist_velocity(kp, self.L_WRIST, valid)
        r_vel, r_accel = self._update_wrist_velocity(kp, self.R_WRIST, valid)

        # 速い方を採用
        best_vel, best_accel = None, None
        if l_vel is not None and r_vel is not None:
            if abs(l_vel) >= abs(r_vel):
                best_vel, best_accel = l_vel, l_accel
            else:
                best_vel, best_accel = r_vel, r_accel
        elif l_vel is not None:
            best_vel, best_accel = l_vel, l_accel
        elif r_vel is not None:
            best_vel, best_accel = r_vel, r_accel

        # ヒステリシス: 発火後、速度が再アーム閾値以下に落ちたら再アーム
        if best_vel is not None and abs(best_vel) < self.strum_rearm_threshold:
            self.strum_armed = True

        if best_vel is None or abs(best_vel) < self.strum_velocity_threshold:
            return None

        # 再アームされていなければ発火しない
        if not self.strum_armed:
            return None

        if now - self.last_strum_time < self.strum_debounce:
            return None

        self.last_strum_time = now
        self.strum_armed = False  # 発火したらロック、速度が落ちるまで再発火しない

        direction = "DOWN" if best_vel > 0 else "UP"

        if best_accel > self.accel_heavy:
            intensity = "HEAVY"
        elif best_accel > self.accel_light:
            intensity = "MEDIUM"
        else:
            intensity = "LIGHT"

        return {
            "type": "STRUM",
            "label": f"STRUM {direction} [{intensity}]",
            "direction": direction,
            "intensity": intensity,
        }

    def _detect_jump(self, kp, now, frame_h, valid):
        """両足首のY座標が同時に大きく上昇（Y値が減少）したらジャンプ"""
        if not (valid(self.L_ANKLE) and valid(self.R_ANKLE)):
            self.prev_l_ankle_y = None
            self.prev_r_ankle_y = None
            return None

        l_ankle_y = kp[self.L_ANKLE][1]
        r_ankle_y = kp[self.R_ANKLE][1]

        if self.prev_l_ankle_y is None:
            self.prev_l_ankle_y = l_ankle_y
            self.prev_r_ankle_y = r_ankle_y
            return None

        # Y軸は画面上が0なので、上昇=値の減少
        l_delta = self.prev_l_ankle_y - l_ankle_y
        r_delta = self.prev_r_ankle_y - r_ankle_y

        self.prev_l_ankle_y = l_ankle_y
        self.prev_r_ankle_y = r_ankle_y

        threshold = frame_h * 0.05  # 画面高さの5%

        if l_delta > threshold and r_delta > threshold:
            if now - self.last_jump_time < self.jump_cooldown:
                return None
            self.last_jump_time = now
            return {"type": "JUMP", "label": "JUMP!"}

        return None

    def _detect_lean_back(self, kp, valid):
        """肩中点〜腰中点のベクトルが垂直から後方に20度以上"""
        if not (valid(self.L_SHOULDER) and valid(self.R_SHOULDER)
                and valid(self.L_HIP) and valid(self.R_HIP)):
            return None

        shoulder_mid_x = (kp[self.L_SHOULDER][0] + kp[self.R_SHOULDER][0]) / 2
        shoulder_mid_y = (kp[self.L_SHOULDER][1] + kp[self.R_SHOULDER][1]) / 2
        hip_mid_x = (kp[self.L_HIP][0] + kp[self.R_HIP][0]) / 2
        hip_mid_y = (kp[self.L_HIP][1] + kp[self.R_HIP][1]) / 2

        # 腰→肩のベクトル（画面座標系: Y下向き）
        dx = shoulder_mid_x - hip_mid_x
        dy = hip_mid_y - shoulder_mid_y  # 反転して上向き正

        # 垂直（上向き）からの角度
        angle = math.degrees(math.atan2(dx, dy))

        # ミラー表示なので、画面上で左に傾く＝実際は後ろにのけぞり
        # 角度の正負は左右反転後の向きで判定
        if abs(angle) > self.lean_back_angle_threshold:
            return {
                "type": "LEAN_BACK",
                "label": "LEAN BACK",
                "angle": round(angle, 1),
            }

        return None

    def _detect_arms_up(self, kp, valid):
        """両手首が両肩より上（Y座標が小さい）"""
        if not (valid(self.L_WRIST) and valid(self.R_WRIST)
                and valid(self.L_SHOULDER) and valid(self.R_SHOULDER)):
            return None

        l_wrist_y = kp[self.L_WRIST][1]
        r_wrist_y = kp[self.R_WRIST][1]
        l_shoulder_y = kp[self.L_SHOULDER][1]
        r_shoulder_y = kp[self.R_SHOULDER][1]

        if l_wrist_y < l_shoulder_y and r_wrist_y < r_shoulder_y:
            return {"type": "ARMS_UP", "label": "ARMS UP \u2014 BREAK!"}

        return None

    def _detect_pitch(self, kp, frame_h, valid):
        """手首のY座標で3段階ピッチ判定（常時表示）。高い方の手を使用"""
        l_valid = valid(self.L_WRIST)
        r_valid = valid(self.R_WRIST)

        if not l_valid and not r_valid:
            return None

        # 両方有効なら高い方（Y値が小さい＝ネック寄り）を使う
        if l_valid and r_valid:
            wrist_y = min(kp[self.L_WRIST][1], kp[self.R_WRIST][1])
        elif l_valid:
            wrist_y = kp[self.L_WRIST][1]
        else:
            wrist_y = kp[self.R_WRIST][1]

        ratio = wrist_y / frame_h

        if ratio < 1 / 3:
            level = "HIGH"
        elif ratio < 2 / 3:
            level = "MID"
        else:
            level = "LOW"

        return {"type": "PITCH", "label": f"PITCH: {level}", "level": level}
