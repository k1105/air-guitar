#!/usr/bin/env python3
"""音源分離: Demucs (htdemucs_6s) で6ステムに分離する。"""

import sys
import subprocess
from pathlib import Path


def separate(audio_path: str, output_dir: str = "separated", model: str = "htdemucs_6s"):
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"{audio_path} が見つかりません")

    venv_python = str(Path(__file__).parent / "venv" / "bin" / "python")

    cmd = [
        venv_python, "-m", "demucs",
        "--name", model,
        "--out", output_dir,
        str(audio_path),
    ]

    print(f"音源分離中: {audio_path.name} (モデル: {model})")

    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
    if result.returncode != 0:
        raise RuntimeError("音源分離に失敗しました")

    stem_dir = Path(output_dir) / model / audio_path.stem
    print(f"完了: {stem_dir}/")
    return stem_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <audio_file> [output_dir]")
        sys.exit(1)
    separate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "separated")
