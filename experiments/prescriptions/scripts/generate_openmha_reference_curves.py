#!/usr/bin/env python3
"""Generate stationary one-microphone openMHA reference curves."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


WORKSPACE = Path(__file__).resolve().parents[3]
GENERATED = WORKSPACE / "experiments" / "prescriptions" / "generated"
CAMPAIGN = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
)
OUTPUT_DIR = CAMPAIGN / "expected" / "openmha"
PROFILES = ("N1", "N2", "N3", "N4", "N5", "N6", "N7", "S1", "S2", "S3")
LEVELS = (45, 65, 85)


def rms_dbfs(signal: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(signal, dtype=np.float64))))
    return 20.0 * math.log10(max(rms, 1e-30))


def frequency_grid(points_per_octave: int) -> np.ndarray:
    count = int(math.floor(points_per_octave * math.log2(10000.0 / 100.0))) + 1
    values = 100.0 * 2.0 ** (np.arange(count, dtype=float) / points_per_octave)
    if values[-1] < 9999.0:
        values = np.append(values, 10000.0)
    return values


def make_stimulus(
    frequencies: np.ndarray,
    level_db_spl: int,
    sample_rate: int,
    settling_seconds: float,
    analysis_seconds: float,
) -> tuple[np.ndarray, int, int]:
    segment_samples = round((settling_seconds + analysis_seconds) * sample_rate)
    analysis_samples = round(analysis_seconds * sample_rate)
    target_dbfs = float(level_db_spl) - 100.0
    amplitude = math.sqrt(2.0) * 10.0 ** (target_dbfs / 20.0)
    segments = []
    time = np.arange(segment_samples, dtype=float) / sample_rate
    for frequency in frequencies:
        segments.append(amplitude * np.sin(2.0 * math.pi * frequency * time))
    mono = np.concatenate(segments)
    return np.column_stack([mono, mono, mono, mono]), segment_samples, analysis_samples


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, action="append")
    parser.add_argument("--mha", default="/usr/local/bin/mha")
    parser.add_argument("--points-per-octave", type=int, default=24)
    parser.add_argument("--settling-seconds", type=float, default=0.5)
    parser.add_argument("--analysis-seconds", type=float, default=0.15)
    args = parser.parse_args()
    profiles = tuple(args.profile) if args.profile else PROFILES
    frequencies = frequency_grid(args.points_per_octave)
    sample_rate = 44_100
    input_dir = GENERATED / "inputs"
    output_audio_dir = GENERATED / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_audio_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, object]] = []

    for profile in profiles:
        cfg_relative = Path("openmha_cfg") / "one_mic_reference" / f"{profile}.cfg"
        cfg = GENERATED / cfg_relative
        if not cfg.is_file():
            raise FileNotFoundError(cfg)
        profile_rows: list[dict[str, object]] = []
        for level in LEVELS:
            stimulus, segment_samples, analysis_samples = make_stimulus(
                frequencies,
                level,
                sample_rate,
                args.settling_seconds,
                args.analysis_seconds,
            )
            input_file = input_dir / f"{profile}_4ch.wav"
            output_file = output_audio_dir / f"{profile}_openmha.wav"
            log_file = OUTPUT_DIR / f"{profile}_{level}dBSPL_openmha.log"
            sf.write(input_file, stimulus, sample_rate, subtype="FLOAT")
            if output_file.exists():
                output_file.unlink()
            subprocess.run(
                [
                    args.mha,
                    "-q",
                    f"--log={log_file}",
                    f"?read:{cfg_relative}",
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
                    f"Unexpected openMHA output for {profile}: "
                    f"rate={output_sample_rate}, shape={output.shape}"
                )
            usable_samples = min(stimulus.shape[0], output.shape[0])
            if usable_samples < stimulus.shape[0] - 2 * segment_samples:
                raise RuntimeError(f"Unexpectedly short openMHA output for {profile}")
            for index, frequency in enumerate(frequencies):
                end = min((index + 1) * segment_samples, usable_samples)
                start = end - analysis_samples
                if start < index * segment_samples:
                    raise RuntimeError(f"Insufficient steady-state window at {frequency} Hz")
                input_dbfs = rms_dbfs(stimulus[start:end, 0])
                left_dbfs = rms_dbfs(output[start:end, 0])
                right_dbfs = rms_dbfs(output[start:end, 1])
                digital_change_left = left_dbfs - input_dbfs
                digital_change_right = right_dbfs - input_dbfs
                row = {
                    "profile": profile,
                    "level_db_spl": level,
                    "frequency_hz": f"{frequency:.9f}",
                    "input_rms_dbfs": f"{input_dbfs:.9f}",
                    "output_rms_dbfs_left": f"{left_dbfs:.9f}",
                    "output_rms_dbfs_right": f"{right_dbfs:.9f}",
                    "digital_level_change_db_left": f"{digital_change_left:.9f}",
                    "digital_level_change_db_right": f"{digital_change_right:.9f}",
                    "calibrated_gain_db": f"{digital_change_left + 20.0:.9f}",
                    "left_right_difference_db": f"{left_dbfs-right_dbfs:.9f}",
                    "settling_seconds": f"{args.settling_seconds:.6f}",
                    "analysis_seconds": f"{args.analysis_seconds:.6f}",
                    "sample_rate_hz": sample_rate,
                    "baseline": "Clarity CEC1 one_mic_reference; calibrated gain = digital change + 20 dB",
                }
                profile_rows.append(row)
                all_rows.append(row)
            input_file.unlink(missing_ok=True)
            output_file.unlink(missing_ok=True)
        write_csv(OUTPUT_DIR / f"{profile}_openmha_reference.csv", profile_rows)
        maximum_lr_difference = max(
            abs(float(row["left_right_difference_db"])) for row in profile_rows
        )
        if maximum_lr_difference > 1e-5:
            raise RuntimeError(
                f"Symmetric {profile} openMHA output differs by "
                f"{maximum_lr_difference:.9f} dB between ears"
            )
        print(f"Generated openMHA reference for {profile}: {len(profile_rows)} points")

    write_csv(OUTPUT_DIR / "openmha_reference_all_profiles.csv", all_rows)
    metadata = {
        "profiles": list(profiles),
        "levels_db_spl": list(LEVELS),
        "frequency_start_hz": float(frequencies[0]),
        "frequency_end_hz": float(frequencies[-1]),
        "frequency_points": len(frequencies),
        "points_per_octave": args.points_per_octave,
        "settling_seconds": args.settling_seconds,
        "analysis_seconds": args.analysis_seconds,
        "sample_rate_hz": sample_rate,
        "input_calibration": "0 dBFS = 100 dB SPL",
        "output_calibration": "0 dBFS = 120 dB SPL",
        "calibrated_gain_equation": "output_dBFS - input_dBFS + 20 dB",
        "clarity_commit": "9df6486fb0bddc7619b3b99f1b3a5c72c109a3ec",
        "openmha": "4.17.0 (444d2cba8866)",
        "config_sha256": {
            profile: hashlib.sha256(
                (GENERATED / "openmha_cfg" / "one_mic_reference" / f"{profile}.cfg").read_bytes()
            ).hexdigest()
            for profile in profiles
        },
    }
    (OUTPUT_DIR / "OPENMHA_REFERENCE_METADATA.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(all_rows)} total openMHA reference points to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
