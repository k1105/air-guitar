/**
 * timeline.js — コードタイムライン描画 + プレイヘッド
 */

let timelineEl = null;
let playheadEl = null;

export function initTimeline(el) {
  timelineEl = el;
}

export function renderTimeline(chordData, duration) {
  if (!timelineEl) return;
  timelineEl.innerHTML = "";
  if (!chordData || !duration) return;

  chordData.forEach((entry, i) => {
    const start = entry.timestamp;
    const end = entry.end_time || (i + 1 < chordData.length ? chordData[i + 1].timestamp : duration);
    const leftPct = (start / duration) * 100;
    const widthPct = ((end - start) / duration) * 100;

    const block = document.createElement("div");
    block.className = "chord-block";
    block.style.left = leftPct + "%";
    block.style.width = widthPct + "%";
    block.dataset.index = i;

    if (entry.chord !== "N" && widthPct > 2) {
      block.textContent = entry.chord;
    }
    timelineEl.appendChild(block);
  });

  playheadEl = document.createElement("div");
  playheadEl.className = "playhead";
  timelineEl.appendChild(playheadEl);
}

export function renderBeatMarkers(beats, duration) {
  if (!timelineEl || !beats || !duration) return;
  // 既存のマーカーを削除
  timelineEl.querySelectorAll(".beat-marker").forEach(el => el.remove());

  for (const t of beats) {
    const pct = (t / duration) * 100;
    const marker = document.createElement("div");
    marker.className = "beat-marker";
    marker.style.left = pct + "%";
    timelineEl.appendChild(marker);
  }
}

export function updateTimeline(currentTime, chordData, duration) {
  if (!timelineEl || !chordData || !duration) return;

  const blocks = timelineEl.querySelectorAll(".chord-block");
  blocks.forEach((block, i) => {
    const entry = chordData[i];
    if (!entry) return;
    const end = entry.end_time || (i + 1 < chordData.length ? chordData[i + 1].timestamp : duration);
    block.classList.toggle("active", currentTime >= entry.timestamp && currentTime < end);
  });

  if (playheadEl) {
    playheadEl.style.left = (currentTime / duration * 100) + "%";
  }
}

export function getChordAt(t, chordData) {
  if (!chordData) return null;
  let chord = null;
  for (const entry of chordData) {
    if (entry.timestamp <= t) {
      chord = entry.chord;
    } else {
      break;
    }
  }
  return chord;
}

// --- ビートグリッド ---
let beatGrid = null;     // 元のビート（4分音符）
let subBeatGrid = null;  // 8分音符グリッド（ビート間に中間点を挿入）
let halfBeatInterval = 0.25; // ビート間隔の半分（スナップ許容幅）

export function setBeatGrid(beats) {
  beatGrid = beats;
  if (!beats || beats.length < 2) {
    subBeatGrid = beats;
    halfBeatInterval = 0.25;
    return;
  }

  // ビート間隔の中央値を算出
  const intervals = [];
  for (let i = 1; i < beats.length; i++) {
    intervals.push(beats[i] - beats[i - 1]);
  }
  intervals.sort((a, b) => a - b);
  const medianInterval = intervals[Math.floor(intervals.length / 2)];
  halfBeatInterval = medianInterval / 2;

  // 8分音符グリッド生成（各ビート間に中間点を挿入）
  subBeatGrid = [];
  for (let i = 0; i < beats.length; i++) {
    subBeatGrid.push(beats[i]);
    if (i + 1 < beats.length) {
      subBeatGrid.push((beats[i] + beats[i + 1]) / 2);
    }
  }
}

/**
 * クオンタイズ: 現在時刻を最寄りの8分音符グリッドにスナップする
 *
 * スナップ許容幅はビート間隔の半分（= 8分音符1個分）で自動計算。
 * 拍の直前 → 次の拍まで待って発音
 * 拍の直後 → 即発音（十分近いのでOK）
 */
export function quantize(t, chordData, duration) {
  if (!chordData || chordData.length === 0) {
    return { chord: null, delay: 0 };
  }

  const grid = subBeatGrid || beatGrid;
  if (!grid || grid.length === 0) {
    // フォールバック: スナップなし
    const chord = getChordAt(t, chordData);
    return { chord, delay: 0 };
  }

  // 二分探索で最寄りのグリッドポイントを見つける
  let lo = 0, hi = grid.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (grid[mid] < t) lo = mid + 1;
    else hi = mid;
  }

  // 前後のグリッド点と比較
  const candidates = [];
  if (lo > 0) candidates.push(grid[lo - 1]);
  if (lo < grid.length) candidates.push(grid[lo]);
  if (lo + 1 < grid.length) candidates.push(grid[lo + 1]);

  let bestPoint = t;
  let bestDist = Infinity;
  for (const pt of candidates) {
    const dist = Math.abs(pt - t);
    if (dist < bestDist) {
      bestDist = dist;
      bestPoint = pt;
    }
  }

  // スナップ許容幅以内か
  if (bestDist > halfBeatInterval) {
    // 遠すぎ → スナップしない
    const chord = getChordAt(t, chordData);
    return { chord, delay: 0 };
  }

  let delay = bestPoint - t;

  // 過去のグリッド点（拍の直後に叩いた） → 即再生で良い
  if (delay < 0) delay = 0;

  // スナップ先の時刻でコードを決定
  const snappedT = t + delay;
  const chord = getChordAt(snappedT, chordData) || getChordAt(t, chordData);

  return { chord, delay };
}
