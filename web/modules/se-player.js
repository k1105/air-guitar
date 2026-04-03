/**
 * se-player.js — SE (効果音) MP3 読み込み+再生
 */

const SE_FILES = {
  strum_down_light:  "se/strum_down_light.mp3",
  strum_down_medium: "se/strum_down_medium.mp3",
  strum_down_heavy:  "se/strum_down_heavy.mp3",
  strum_up_light:    "se/strum_up_light.mp3",
  strum_up_medium:   "se/strum_up_medium.mp3",
  strum_up_heavy:    "se/strum_up_heavy.mp3",
  jump:              "se/jump.mp3",
  lean_back:         "se/lean_back.mp3",
  arms_up_start:     "se/arms_up_start.mp3",
  arms_up_end:       "se/arms_up_end.mp3",
  climax:            "se/climax.mp3",
  energy_up:         "se/energy_up.mp3",
  energy_down:       "se/energy_down.mp3",
};

let audioCtx = null;
const audioBuffers = {};

export async function initSE() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const entries = Object.entries(SE_FILES);
  await Promise.all(entries.map(async ([key, path]) => {
    try {
      const res = await fetch(path);
      const buf = await res.arrayBuffer();
      audioBuffers[key] = await audioCtx.decodeAudioData(buf);
    } catch (e) {
      console.warn(`SE load failed: ${path}`, e);
    }
  }));
  console.log(`Loaded ${Object.keys(audioBuffers).length}/${entries.length} SE files`);
}

export function resumeAudioCtx() {
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
}

export function playSE(key, volume = 1.0) {
  if (!audioCtx) return null;
  const buffer = audioBuffers[key];
  if (!buffer) return null;
  const source = audioCtx.createBufferSource();
  const gain = audioCtx.createGain();
  source.buffer = buffer;
  gain.gain.value = volume;
  source.connect(gain);
  gain.connect(audioCtx.destination);
  source.start();
  return source;
}

// LEAN BACK ループ
let leanBackSource = null;
let leanBackActive = false;

export function startLeanBackLoop() {
  if (leanBackActive || !audioCtx) return;
  leanBackActive = true;
  const buffer = audioBuffers.lean_back;
  if (!buffer) return;
  leanBackSource = audioCtx.createBufferSource();
  const gain = audioCtx.createGain();
  leanBackSource.buffer = buffer;
  leanBackSource.loop = true;
  gain.gain.value = 0.6;
  leanBackSource.connect(gain);
  gain.connect(audioCtx.destination);
  leanBackSource.start();
}

export function stopLeanBackLoop() {
  if (!leanBackActive) return;
  leanBackActive = false;
  if (leanBackSource) {
    leanBackSource.stop();
    leanBackSource = null;
  }
}
