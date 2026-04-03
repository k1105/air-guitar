#!/usr/bin/env python3
"""音源からコード進行を抽出しJSON出力する。"""

import sys
import os
import json
from pathlib import Path

if not os.getenv('VAMP_PATH'):
    default_vamp = os.path.expanduser('~/Library/Audio/Plug-Ins/Vamp')
    if os.path.isdir(default_vamp):
        os.environ['VAMP_PATH'] = default_vamp

from chord_extractor.extractors import Chordino


def extract_and_save(audio_path: str, output_path: str, guitar_stem_path: str = None):
    """コード抽出してJSONに保存。guitar_stem_pathがあればそちらを解析。"""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"{audio_path} が見つかりません")

    target = audio_path
    if guitar_stem_path:
        gp = Path(guitar_stem_path)
        if gp.exists():
            print(f"ギターパート検出: {gp}")
            target = gp

    chordino = Chordino(roll_on=1)
    print(f"コード抽出中: {target.name} ...")
    chords = chordino.extract(str(target))

    result = []
    for i, change in enumerate(chords):
        entry = {
            "chord": change.chord,
            "timestamp": round(change.timestamp, 6),
        }
        if i + 1 < len(chords):
            entry["end_time"] = round(chords[i + 1].timestamp, 6)
        result.append(entry)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"完了: {output_path} ({len(result)} コード)")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <audio_file> <output_json> [guitar_stem]")
        sys.exit(1)
    extract_and_save(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
