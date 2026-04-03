/**
 * chord-engine.js — コードボイシング + Tone.js PluckSynth + playGuitarChord
 */

// --- Chord → MIDI note mapping (guitar voicings) ---
const CHORD_VOICINGS = {
  'C':   ['C3','E3','G3','C4','E4'],
  'D':   ['D3','A3','D4','F#4'],
  'E':   ['E2','B2','E3','G#3','B3','E4'],
  'F':   ['F2','C3','F3','A3','C4','F4'],
  'G':   ['G2','B2','D3','G3','B3','G4'],
  'A':   ['A2','E3','A3','C#4','E4'],
  'B':   ['B2','F#3','B3','D#4','F#4'],
  'Db':  ['Db3','Ab3','Db4','F4'],
  'Eb':  ['Eb3','Bb3','Eb4','G4'],
  'Gb':  ['Gb2','Db3','Gb3','Bb3','Db4'],
  'Ab':  ['Ab2','Eb3','Ab3','C4','Eb4'],
  'Bb':  ['Bb2','F3','Bb3','D4','F4'],
  'Cm':  ['C3','Eb3','G3','C4','Eb4'],
  'Dm':  ['D3','A3','D4','F4'],
  'Em':  ['E2','B2','E3','G3','B3','E4'],
  'Fm':  ['F2','C3','F3','Ab3','C4'],
  'Gm':  ['G2','Bb2','D3','G3','Bb3'],
  'Am':  ['A2','E3','A3','C4','E4'],
  'Bm':  ['B2','F#3','B3','D4','F#4'],
  'Dbm': ['Db3','Ab3','Db4','E4'],
  'Ebm': ['Eb3','Bb3','Eb4','Gb4'],
  'Gbm': ['Gb2','Db3','Gb3','A3'],
  'Abm': ['Ab2','Eb3','Ab3','B3','Eb4'],
  'Bbm': ['Bb2','F3','Bb3','Db4','F4'],
  'C7':  ['C3','E3','Bb3','C4','E4'],
  'D7':  ['D3','A3','C4','F#4'],
  'E7':  ['E2','B2','D3','G#3','B3','E4'],
  'F7':  ['F2','C3','Eb3','A3','C4'],
  'G7':  ['G2','B2','D3','F3','G3','B3'],
  'A7':  ['A2','E3','G3','C#4','E4'],
  'B7':  ['B2','F#3','A3','D#4','F#4'],
  'Cm7': ['C3','Eb3','Bb3','C4'],
  'Dm7': ['D3','A3','C4','F4'],
  'Em7': ['E2','B2','D3','G3','B3'],
  'Fm7': ['F2','C3','Eb3','Ab3'],
  'Gm7': ['G2','Bb2','D3','F3'],
  'Am7': ['A2','E3','G3','C4','E4'],
  'Bm7': ['B2','F#3','A3','D4'],
};

const ENHARMONIC = {
  'C#': 'Db', 'D#': 'Eb', 'F#': 'Gb', 'G#': 'Ab', 'A#': 'Bb',
  'C#m': 'Dbm', 'D#m': 'Ebm', 'F#m': 'Gbm', 'G#m': 'Abm', 'A#m': 'Bbm',
};

function resolveVoicing(chordName) {
  if (chordName === 'N' || !chordName) return null;
  if (CHORD_VOICINGS[chordName]) return CHORD_VOICINGS[chordName];
  const en = ENHARMONIC[chordName];
  if (en && CHORD_VOICINGS[en]) return CHORD_VOICINGS[en];
  for (let len = chordName.length - 1; len >= 1; len--) {
    const sub = chordName.substring(0, len);
    if (CHORD_VOICINGS[sub]) return CHORD_VOICINGS[sub];
    const enSub = ENHARMONIC[sub];
    if (enSub && CHORD_VOICINGS[enSub]) return CHORD_VOICINGS[enSub];
  }
  return null;
}

function shiftOctave(noteName, offset) {
  if (offset === 0) return noteName;
  const match = noteName.match(/^([A-G][#b]?)(\d+)$/);
  if (!match) return noteName;
  return match[1] + (parseInt(match[2]) + offset);
}

// --- PluckSynth Pool ---
const POOL_SIZE = 12;
let pluckPool = [];
let toneStarted = false;

function ensurePool() {
  if (pluckPool.length > 0) return;
  for (let i = 0; i < POOL_SIZE; i++) {
    const p = new Tone.PluckSynth({
      attackNoise: 1.5,
      dampening: 2800,
      resonance: 0.99,
    }).toDestination();
    p.volume.value = -6;
    pluckPool.push(p);
  }
}

export async function initTone() {
  if (toneStarted) return;
  Tone.setContext(new Tone.Context({ latencyHint: 'interactive', lookAhead: 0 }));
  await Tone.start();
  ensurePool();
  // ウォームアップ: 無音で全シンセを叩く
  pluckPool.forEach(p => { p.volume.value = -Infinity; p.triggerAttack('C3'); });
  setTimeout(() => pluckPool.forEach(p => { p.volume.value = -6; }), 100);
  toneStarted = true;
}

// フロントエンド側クールダウン（バックエンドと二重防御）
let lastChordTime = 0;
const CHORD_COOLDOWN_MS = 120;

/**
 * コードを再生する
 * @param {string} chordName - コード名 (e.g. "Am")
 * @param {number} octaveOffset - オクターブシフト (-1, 0, +1)
 * @param {string} intensity - "LIGHT" | "MEDIUM" | "HEAVY"
 * @param {number} delay - クオンタイズ遅延（秒）。グリッドに合わせるための待ち時間
 */
export function playGuitarChord(chordName, octaveOffset = 0, intensity = "MEDIUM", delay = 0) {
  const now = performance.now();
  if (now - lastChordTime < CHORD_COOLDOWN_MS) return;
  lastChordTime = now;

  const notes = resolveVoicing(chordName);
  if (!notes) return;

  ensurePool();

  const shifted = octaveOffset === 0 ? notes : notes.map(n => shiftOctave(n, octaveOffset));

  const volume = intensity === "HEAVY" ? -3 : intensity === "LIGHT" ? -12 : -6;
  const stagger = intensity === "HEAVY" ? 0.010 : intensity === "LIGHT" ? 0.025 : 0.015;

  const tNow = Tone.immediate() + delay;

  pluckPool.forEach(p => {
    p.volume.value = volume;
  });

  shifted.forEach((note, i) => {
    const s = pluckPool[i % POOL_SIZE];
    s.triggerAttack(note, tNow + i * stagger);
  });
}

export { resolveVoicing };
