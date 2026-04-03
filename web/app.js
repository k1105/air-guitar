/**
 * app.js — Air Guitar Production メインコーディネーター
 * Prep画面 / Perform画面の切り替え + 共有状態管理
 */

import { initTone, playGuitarChord } from "./modules/chord-engine.js";
import { initSE, resumeAudioCtx } from "./modules/se-player.js";
import { initTimeline, renderTimeline, renderBeatMarkers, getChordAt, setBeatGrid } from "./modules/timeline.js";
import { handleGesture, getCurrentPitch } from "./modules/gesture-handler.js";

// ============================================================
// State
// ============================================================
let currentSong = null;   // { name, duration, chord_count, has_backing }
let chordData = null;
let audioDuration = 0;
let audioElement = null;
let isPlaying = false;
let animFrameId = null;
let ws = null;

// ============================================================
// DOM
// ============================================================
const body = document.body;

// Prep
const uploadArea = document.getElementById("uploadArea");
const audioUpload = document.getElementById("audioUpload");
const prepProgress = document.getElementById("prepProgress");
const progressLabel = document.getElementById("progressLabel");
const progressFill = document.getElementById("progressFill");
const songsContainer = document.getElementById("songs");

// Perform
const backBtn = document.getElementById("backBtn");
const songTitle = document.getElementById("songTitle");
const timeDisplay = document.getElementById("timeDisplay");
const playBtn = document.getElementById("playBtn");
const backingToggle = document.getElementById("backingToggle");
const canvas = document.getElementById("skeleton");
const ctx = canvas.getContext("2d");
const currentChordEl = document.getElementById("currentChord");
const cueLabels = document.getElementById("cueLabels");
const pitchIndicator = document.getElementById("pitchIndicator");
const historyList = document.getElementById("historyList");
const wsStatus = document.getElementById("wsStatus");
const bpmDisplay = document.getElementById("bpmDisplay");
const timelineEl = document.getElementById("timeline");

// ============================================================
// Init
// ============================================================
initTimeline(timelineEl);
initSE();
loadSongList();
connectWS();

document.addEventListener("click", () => resumeAudioCtx(), { once: true });

function resizeCanvas() {
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;
}
window.addEventListener("resize", resizeCanvas);

// ============================================================
// Screen Navigation
// ============================================================
function showPrep() {
  stopPlayback();
  body.className = "screen-prep";
  loadSongList();
}

function showPerform(song) {
  currentSong = song;
  body.className = "screen-perform";
  songTitle.textContent = song.name;
  resizeCanvas();
  loadSongData(song);
}

backBtn.addEventListener("click", showPrep);

// ============================================================
// Prep: Upload
// ============================================================
uploadArea.addEventListener("click", () => audioUpload.click());
uploadArea.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadArea.classList.add("dragover");
});
uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
uploadArea.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadArea.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});
audioUpload.addEventListener("change", (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
  prepProgress.hidden = false;
  progressLabel.textContent = "アップロード中...";
  progressFill.style.width = "5%";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/prep", { method: "POST", body: formData });
    const data = await res.json();
    if (data.error) {
      progressLabel.textContent = `エラー: ${data.error}`;
    }
    // 進捗はWebSocketで受信する
  } catch (err) {
    progressLabel.textContent = `アップロード失敗: ${err.message}`;
  }
}

// ============================================================
// Prep: Song List
// ============================================================
async function loadSongList() {
  try {
    const res = await fetch("/api/songs");
    const songs = await res.json();
    renderSongList(songs);
  } catch (e) {
    // サーバー未起動時は空
    songsContainer.innerHTML = "";
  }
}

function renderSongList(songs) {
  songsContainer.innerHTML = "";
  if (songs.length === 0) {
    songsContainer.innerHTML = '<div style="color:#555">まだ曲がありません</div>';
    return;
  }
  for (const song of songs) {
    const card = document.createElement("div");
    card.className = "song-card";
    card.innerHTML = `
      <div class="name">${song.name}</div>
      <div class="meta">${formatTime(song.duration)} | ${song.bpm || '?'} BPM | ${song.chord_count} chords</div>
      <button class="btn-perform">Perform</button>
    `;
    card.querySelector(".btn-perform").addEventListener("click", (e) => {
      e.stopPropagation();
      showPerform(song);
    });
    songsContainer.appendChild(card);
  }
}

// ============================================================
// Perform: Load Song Data
// ============================================================
async function loadSongData(song) {
  // コードJSON読み込み
  try {
    const res = await fetch(`/api/songs/${song.name}/chords.json`);
    chordData = await res.json();
  } catch (e) {
    console.error("Failed to load chords:", e);
    chordData = null;
  }

  // ビートグリッド読み込み
  let loadedBpm = null;
  let loadedBeats = null;
  try {
    const res = await fetch(`/api/songs/${song.name}/beats.json`);
    const beatsData = await res.json();
    loadedBeats = beatsData.beats;
    loadedBpm = beatsData.bpm;
    setBeatGrid(loadedBeats);
    console.log(`Beat grid loaded: BPM=${loadedBpm}, ${loadedBeats.length} beats`);
  } catch (e) {
    console.warn("No beat grid available, using chord-boundary fallback");
    setBeatGrid(null);
  }

  // 音源読み込み
  if (audioElement) {
    audioElement.pause();
    audioElement.src = "";
  }
  audioElement = new Audio();
  const trackType = backingToggle.checked && song.has_backing ? "backing.mp3" : `original${getSongExt(song)}`;
  audioElement.src = `/api/songs/${song.name}/${trackType}`;
  audioElement.addEventListener("loadedmetadata", () => {
    audioDuration = audioElement.duration;
    renderTimeline(chordData, audioDuration);
    if (loadedBeats) renderBeatMarkers(loadedBeats, audioDuration);
    updateTimeDisplay();
    // BPM表示
    bpmDisplay.textContent = loadedBpm ? `${loadedBpm} BPM` : "";
  });
  audioElement.addEventListener("ended", () => {
    isPlaying = false;
    playBtn.textContent = "Play";
    cancelAnimationFrame(animFrameId);
  });

  backingToggle.addEventListener("change", () => {
    const wasPlaying = isPlaying;
    const currentTime = audioElement ? audioElement.currentTime : 0;
    const type = backingToggle.checked && song.has_backing ? "backing.mp3" : `original${getSongExt(song)}`;
    audioElement.src = `/api/songs/${song.name}/${type}`;
    audioElement.addEventListener("loadedmetadata", () => {
      audioElement.currentTime = currentTime;
      if (wasPlaying) audioElement.play();
    }, { once: true });
  });
}

function getSongExt(song) {
  // デフォルトは.mp3
  return ".mp3";
}

// ============================================================
// Perform: Playback Control
// ============================================================
playBtn.addEventListener("click", async () => {
  if (!audioElement) return;

  if (!isPlaying) {
    await initTone();
    resumeAudioCtx();
    audioElement.play();
    isPlaying = true;
    playBtn.textContent = "Pause";
    tick();
  } else {
    audioElement.pause();
    isPlaying = false;
    playBtn.textContent = "Play";
    cancelAnimationFrame(animFrameId);
  }
});

// タイムラインクリックでシーク
timelineEl.addEventListener("click", (e) => {
  if (!audioElement || !audioDuration) return;
  const rect = timelineEl.getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  audioElement.currentTime = pct * audioDuration;
  updateTimeDisplay();
});

function tick() {
  if (!isPlaying) return;
  updateTimeDisplay();

  // 現在のコード表示
  if (chordData && audioElement) {
    const chord = getChordAt(audioElement.currentTime, chordData);
    currentChordEl.textContent = chord && chord !== "N" ? chord : "--";
  }

  animFrameId = requestAnimationFrame(tick);
}

function stopPlayback() {
  if (audioElement) {
    audioElement.pause();
    audioElement.src = "";
  }
  isPlaying = false;
  cancelAnimationFrame(animFrameId);
}

function updateTimeDisplay() {
  if (!audioElement) return;
  timeDisplay.textContent = `${formatTime(audioElement.currentTime)} / ${formatTime(audioDuration)}`;
}

// ============================================================
// WebSocket
// ============================================================
function connectWS() {
  ws = new WebSocket(`ws://${location.hostname}:8765`);

  ws.onopen = () => {
    wsStatus.textContent = "Connected";
    wsStatus.className = "connected";
  };

  ws.onclose = () => {
    wsStatus.textContent = "Disconnected";
    wsStatus.className = "";
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "gesture") {
      handleGestureMessage(data);
    } else if (data.type === "prep_progress") {
      handlePrepProgress(data);
    } else if (data.type === "prep_done") {
      handlePrepDone(data);
    }
  };
}

function handleGestureMessage(data) {
  // Perform画面でのみ処理
  if (body.className !== "screen-perform") return;

  handleGesture(data, {
    canvasCtx: ctx,
    audioElement,
    chordData,
    audioDuration,
    onCue: (type, label) => {
      addCueLabel(type, label);
      addHistory(type, label);

      // コード表示フラッシュ
      if (type === "STRUM" || type === "JUMP") {
        currentChordEl.classList.add("flash");
        setTimeout(() => currentChordEl.classList.remove("flash"), 100);
      }
    },
  });

  // PITCHインジケーター更新
  pitchIndicator.textContent = `PITCH: ${getCurrentPitch()}`;
}

let cueTimeout = null;
function addCueLabel(type, label) {
  const div = document.createElement("div");
  div.className = `cue-label cue-${type}`;
  div.textContent = label;
  cueLabels.appendChild(div);

  if (cueTimeout) clearTimeout(cueTimeout);
  cueTimeout = setTimeout(() => {
    cueLabels.innerHTML = "";
    cueTimeout = null;
  }, 500);
}

function addHistory(type, label) {
  const li = document.createElement("li");
  li.className = `cue-color-${type}`;
  li.textContent = `${new Date().toLocaleTimeString("ja-JP")} ${label}`;
  historyList.prepend(li);
  while (historyList.children.length > 15) {
    historyList.removeChild(historyList.lastChild);
  }
}

function handlePrepProgress(data) {
  prepProgress.hidden = false;
  const stageNames = {
    copying: "ファイルコピー中...",
    separating: "音源分離中 (Demucs)...",
    extracting: "コード抽出中 (Chordino)...",
    backing: "バッキングトラック生成中...",
    analyzing_beats: "BPM/ビート解析中 (librosa)...",
    error: "エラーが発生しました",
  };
  progressLabel.textContent = stageNames[data.stage] || data.stage;
  progressFill.style.width = Math.max(5, data.progress * 100) + "%";
}

function handlePrepDone(data) {
  progressLabel.textContent = `${data.song} の準備が完了しました`;
  progressFill.style.width = "100%";
  setTimeout(() => {
    prepProgress.hidden = true;
    loadSongList();
  }, 1500);
}

// ============================================================
// Utils
// ============================================================
function formatTime(s) {
  if (!s || isNaN(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
