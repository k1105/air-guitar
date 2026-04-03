/**
 * gesture-handler.js — WebSocket受信 → コード合成 + SE + 骨格描画 の統合ハンドラ
 */

import { playGuitarChord } from "./chord-engine.js";
import { playSE, startLeanBackLoop, stopLeanBackLoop } from "./se-player.js";
import { drawSkeleton } from "./skeleton-renderer.js";
import { updateTimeline, getChordAt, quantize } from "./timeline.js";
import { updateEnergy } from "./energy.js";

// 状態
let currentPitchLevel = "MID"; // HIGH=+1, MID=0, LOW=-1
let armsUpActive = false;

/**
 * ジェスチャーメッセージを処理する
 * @param {Object} data - WebSocketメッセージ
 * @param {Object} ctx - コンテキスト {canvasCtx, audioElement, chordData, audioDuration, onCue}
 */
export function handleGesture(data, ctx) {
  const { canvasCtx, audioElement, chordData, audioDuration, onCue } = ctx;
  const cues = data.cues || [];
  const cueTypes = data.cue_types || [];
  const keypoints = data.keypoints;

  // 骨格描画
  if (canvasCtx) {
    canvasCtx.clearRect(0, 0, canvasCtx.canvas.width, canvasCtx.canvas.height);
    if (keypoints && keypoints.length === 17) {
      drawSkeleton(canvasCtx, keypoints);
    }
  }

  // タイムライン更新
  if (audioElement && chordData) {
    updateTimeline(audioElement.currentTime, chordData, audioDuration);
  }

  // PITCH更新
  if (data.pitch_level) {
    currentPitchLevel = data.pitch_level;
  }

  // ARMS_UP 状態終了チェック
  if (!cueTypes.includes("ARMS_UP") && armsUpActive) {
    armsUpActive = false;
  }

  // 各キュー処理
  let chordTriggered = false;

  for (let i = 0; i < cueTypes.length; i++) {
    const type = cueTypes[i];
    const label = cues[i];

    if (type === "PITCH") continue;

    if (onCue) onCue(type, label);

    if (type === "STRUM") {
      const detail = data.strum_detail || {};
      const intensity = detail.intensity || "MEDIUM";
      const octaveOffset = currentPitchLevel === "HIGH" ? 1 : currentPitchLevel === "LOW" ? -1 : 0;

      if (!armsUpActive && !chordTriggered && audioElement && chordData) {
        const q = quantize(audioElement.currentTime, chordData, audioDuration);
        if (q.chord && q.chord !== "N") {
          playGuitarChord(q.chord, octaveOffset, intensity, q.delay);
          chordTriggered = true;
        }
      }

    } else if (type === "JUMP") {
      if (!armsUpActive && !chordTriggered && audioElement && chordData) {
        const q = quantize(audioElement.currentTime, chordData, audioDuration);
        if (q.chord && q.chord !== "N") {
          playGuitarChord(q.chord, 0, "HEAVY", q.delay);
          chordTriggered = true;
        }
      }

    } else if (type === "ARMS_UP") {
      if (!armsUpActive) {
        armsUpActive = true;
      }
    }
  }
}

export function getCurrentPitch() {
  return currentPitchLevel;
}
