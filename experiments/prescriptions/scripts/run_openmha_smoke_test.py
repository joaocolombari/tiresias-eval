#!/usr/bin/env python3
"""Run a deterministic offline smoke test through one generated openMHA config."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


WORKSPACE = Path(__file__).resolve().parents[3]
GENERATED = WORKSPACE / "experiments" / "prescriptions" / "generated"


def rms_dbfs(signal: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(signal)))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="N3")
    parser.add_argument("--mha", default="/usr/local/bin/mha")
    args = parser.parse_args()

    profile = args.profile.upper()
    input_dir = GENERATED / "inputs"
    output_dir = GENERATED / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    sample_rate = 44_100
    duration_s = 1.0
    target_rms_dbfs = -30.0
    time = np.arange(round(sample_rate * duration_s)) / sample_rate
    amplitude = np.sqrt(2.0) * 10 ** (target_rms_dbfs / 20.0)
    mono = amplitude * np.sin(2 * np.pi * 1_000.0 * time)
    four_channel = np.column_stack([mono, mono, mono, mono])
    input_file = input_dir / f"{profile}_4ch.wav"
    output_file = output_dir / f"{profile}_openmha.wav"
    sf.write(input_file, four_channel, sample_rate, subtype="FLOAT")

    cfg = Path("openmha_cfg") / "one_mic_reference" / f"{profile}.cfg"
    log = GENERATED / f"openmha_smoke_{profile}.log"
    subprocess.run(
        [
            args.mha,
            "-q",
            f"--log={log}",
            f"?read:{cfg}",
            "cmd=start",
            "cmd=stop",
            "cmd=quit",
        ],
        cwd=GENERATED,
        check=True,
    )

    output, output_sample_rate = sf.read(output_file, always_2d=True)
    if output_sample_rate != sample_rate or output.shape[1] != 2:
        raise RuntimeError(
            f"Unexpected output format: rate={output_sample_rate}, shape={output.shape}"
        )
    result = {
        "profile": profile,
        "stimulus": "1 kHz sine",
        "sample_rate_hz": sample_rate,
        "input_channels": 4,
        "output_channels": 2,
        "input_rms_dbfs": round(rms_dbfs(four_channel[:, 0]), 6),
        "output_rms_dbfs_left": round(rms_dbfs(output[:, 0]), 6),
        "output_rms_dbfs_right": round(rms_dbfs(output[:, 1]), 6),
        "digital_level_change_db_left": round(
            rms_dbfs(output[:, 0]) - rms_dbfs(four_channel[:, 0]), 6
        ),
        "digital_level_change_db_right": round(
            rms_dbfs(output[:, 1]) - rms_dbfs(four_channel[:, 0]), 6
        ),
        "input_level_db_spl": round(rms_dbfs(four_channel[:, 0]) + 100.0, 6),
        "output_level_db_spl_left": round(rms_dbfs(output[:, 0]) + 120.0, 6),
        "output_level_db_spl_right": round(rms_dbfs(output[:, 1]) + 120.0, 6),
        "calibrated_gain_db_left": round(
            (rms_dbfs(output[:, 0]) + 120.0)
            - (rms_dbfs(four_channel[:, 0]) + 100.0),
            6,
        ),
        "calibrated_gain_db_right": round(
            (rms_dbfs(output[:, 1]) + 120.0)
            - (rms_dbfs(four_channel[:, 0]) + 100.0),
            6,
        ),
        "calibration_note": "CEC1 uses 0 dBFS = 100 dB SPL at input and 120 dB SPL at output",
        "config": str(cfg),
    }
    destination = GENERATED / f"openmha_smoke_{profile}.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
