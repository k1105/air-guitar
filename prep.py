"""前処理パイプライン: 音源分離 → コード抽出 → BPM/ビート解析 → バッキングトラック生成"""

import json
import shutil
import subprocess
import time
from pathlib import Path

import librosa
import numpy as np

from separate import separate
from extract_chords import extract_and_save


def create_backing_track(stems_dir: Path, output_path: Path):
    """ギター以外のstemをmixしてバッキングトラックを生成"""
    stem_names = ["drums.wav", "bass.wav", "vocals.wav", "piano.wav", "other.wav"]
    inputs = [str(stems_dir / s) for s in stem_names if (stems_dir / s).exists()]

    if not inputs:
        print("警告: stemが見つかりません。バッキングトラック生成をスキップ")
        return None

    cmd = ["ffmpeg", "-y"]
    for inp in inputs:
        cmd += ["-i", inp]

    cmd += [
        "-filter_complex", f"amix=inputs={len(inputs)}:duration=longest:normalize=0",
        "-b:a", "192k",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"警告: バッキングトラック生成に失敗: {result.stderr.decode()[-200:]}")
        return None

    print(f"バッキングトラック生成完了: {output_path}")
    return output_path


def run_prep(audio_file: str, songs_dir: str = "songs", progress_callback=None):
    """
    前処理パイプラインを実行する。

    Args:
        audio_file: 入力音源ファイルパス
        songs_dir: songs保存ディレクトリ
        progress_callback: fn(stage, progress) — 進捗通知用コールバック

    Returns:
        song_dir: 曲ディレクトリのPath
    """
    audio_path = Path(audio_file)
    song_name = audio_path.stem
    song_dir = Path(songs_dir) / song_name

    song_dir.mkdir(parents=True, exist_ok=True)
    stems_dir = song_dir / "stems"

    def notify(stage, progress):
        if progress_callback:
            progress_callback(stage, progress)
        print(f"[{stage}] {int(progress * 100)}%")

    # 1. 音源コピー
    notify("copying", 0.0)
    dest_audio = song_dir / f"original{audio_path.suffix}"
    if not dest_audio.exists() or dest_audio.stat().st_size != audio_path.stat().st_size:
        shutil.copy2(audio_path, dest_audio)
    notify("copying", 1.0)

    # 2. 音源分離
    notify("separating", 0.0)
    temp_sep_dir = song_dir / "_separated"
    stem_result_dir = separate(str(dest_audio), str(temp_sep_dir))
    # demucsの出力を stems/ に移動
    if stems_dir.exists():
        shutil.rmtree(stems_dir)
    shutil.move(str(stem_result_dir), str(stems_dir))
    # temp cleanup
    shutil.rmtree(temp_sep_dir, ignore_errors=True)
    notify("separating", 1.0)

    # 3. コード抽出
    notify("extracting", 0.0)
    chords_path = song_dir / "chords.json"
    guitar_stem = stems_dir / "guitar.wav"
    extract_and_save(
        str(dest_audio),
        str(chords_path),
        str(guitar_stem) if guitar_stem.exists() else None,
    )
    notify("extracting", 1.0)

    # 4. バッキングトラック生成
    notify("backing", 0.0)
    backing_path = song_dir / "backing.mp3"
    create_backing_track(stems_dir, backing_path)
    notify("backing", 1.0)

    # 5. BPM / ビート解析
    notify("analyzing_beats", 0.0)
    beats_path = song_dir / "beats.json"
    bpm = _analyze_beats(dest_audio, beats_path)
    notify("analyzing_beats", 1.0)

    # 6. メタデータ生成
    duration = _get_duration(dest_audio)
    chord_count = 0
    if chords_path.exists():
        with open(chords_path) as f:
            chord_count = len(json.load(f))

    meta = {
        "name": song_name,
        "duration": duration,
        "bpm": bpm,
        "chord_count": chord_count,
        "has_backing": backing_path.exists(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(song_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    notify("done", 1.0)
    print(f"前処理完了: {song_dir}")
    return song_dir


def _analyze_beats(audio_path: Path, output_path: Path) -> float:
    """librosaでBPMとビート位置を解析してJSONに保存"""
    print(f"BPM/ビート解析中: {audio_path.name} ...")
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # tempoがndarrayの場合（librosaバージョンによる）
        bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        result = {
            "bpm": round(bpm, 1),
            "beats": [round(float(t), 4) for t in beat_times],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"BPM: {bpm:.1f} | ビート数: {len(beat_times)}")
        return round(bpm, 1)
    except Exception as e:
        print(f"警告: ビート解析に失敗: {e}")
        return 0.0


def _get_duration(audio_path: Path) -> float:
    """ffprobeで音源の長さ(秒)を取得"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except (ValueError, FileNotFoundError):
        return 0.0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <audio_file> [songs_dir]")
        sys.exit(1)
    run_prep(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "songs")
