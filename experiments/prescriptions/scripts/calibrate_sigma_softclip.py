#!/usr/bin/env python3
"""Calibrate the Sigma peak-detector LUT coordinates without fitting openMHA."""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CALIBRATION_CSV = (
    ROOT
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
    / "raw"
    / "softclip"
    / "softclip_detector_calibration.csv"
)
SCRIPT_DIR = ROOT / "tiresias-eval-sigma" / "scripts" / "softclip"
NOMINAL_SCRIPT = SCRIPT_DIR / "softclip_apply_cec1.sss"
CALIBRATED_SCRIPT = SCRIPT_DIR / "softclip_apply_cec1_calibrated.sss"
RESULTS_DIR = (
    ROOT
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
    / "processed"
    / "softclip_calibration"
)

IDENTIFICATION_DB_PER_INDEX = -0.5
ADAU_DAC_SINGLE_ENDED_FS_DBV = -6.020599913
SINE_PEAK_OVER_RMS_DB = 3.010299957
THRESHOLD_DBFS_PEAK = -27.036
COMPRESSION_SLOPE = 0.2
CEILING_DBFS_PEAK = -22.0
Q_SCALE = 1 << 23
TRANSPARENT_DELTA_OUTLIER_DB = 0.5
MIN_INCLUDED_POINTS = 8


def target_gain_db(level_dbfs_peak: float) -> tuple[float, float]:
    if level_dbfs_peak <= THRESHOLD_DBFS_PEAK:
        output = level_dbfs_peak
    else:
        compressed = THRESHOLD_DBFS_PEAK + COMPRESSION_SLOPE * (
            level_dbfs_peak - THRESHOLD_DBFS_PEAK
        )
        output = min(compressed, CEILING_DBFS_PEAK)
    return output - level_dbfs_peak, output


def q523_word(linear: float) -> bytes:
    value = round(linear * Q_SCALE)
    if not 0 <= value <= 0x7FFFFFFF:
        raise ValueError(f"5.23 value out of range: {linear}")
    return value.to_bytes(4, "big")


def csharp_word(word: bytes, index: int, level: float, gain: float) -> str:
    values = ", ".join(f"0x{x:02X}" for x in word)
    return (
        f"    new byte[] {{ {values} }}, "
        f"// {index:2d}: input {level:+.6f} dBFS peak, gain {gain:+.6f} dB"
    )


def regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("Calibration input range is zero")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sxx
    intercept = y_mean - slope * x_mean
    fitted = [intercept + slope * x for x in xs]
    ss_res = sum((y - f) ** 2 for y, f in zip(ys, fitted))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot else 1.0
    return intercept, slope, r_squared


def inferred_fractional_index(attenuation_db: float) -> float:
    """Invert the identification LUT, accounting for linear-gain interpolation."""
    approximate = attenuation_db / IDENTIFICATION_DB_PER_INDEX
    lower = max(0, min(43, math.floor(approximate)))
    upper = lower + 1
    lower_gain = 10.0 ** (IDENTIFICATION_DB_PER_INDEX * lower / 20.0)
    upper_gain = 10.0 ** (IDENTIFICATION_DB_PER_INDEX * upper / 20.0)
    measured_gain = 10.0 ** (attenuation_db / 20.0)
    fraction = (measured_gain - lower_gain) / (upper_gain - lower_gain)
    return lower + fraction


def interpolate_with_endpoint_extrapolation(
    query: float, coordinates: list[tuple[float, float]]
) -> float:
    """Piecewise-linear y(x), extrapolating with the first/last segment."""
    if query <= coordinates[0][0]:
        left, right = coordinates[0], coordinates[1]
    elif query >= coordinates[-1][0]:
        left, right = coordinates[-2], coordinates[-1]
    else:
        for left, right in zip(coordinates, coordinates[1:]):
            if left[0] <= query <= right[0]:
                break
    fraction = (query - left[0]) / (right[0] - left[0])
    return left[1] + fraction * (right[1] - left[1])


def main() -> None:
    rows: list[dict[str, float | bool | str]] = []
    with CALIBRATION_CSV.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if not raw["transparent_output_dbv"].strip():
                continue
            source = float(raw["source_input_dbv"])
            transparent = float(raw["transparent_output_dbv"])
            identified = float(raw["identification_output_dbv"])
            attenuation = identified - transparent
            index = inferred_fractional_index(attenuation)
            level_dbfs_peak = (
                transparent
                - ADAU_DAC_SINGLE_ENDED_FS_DBV
                + SINE_PEAK_OVER_RMS_DB
            )
            rows.append(
                {
                    "source_input_dbv": source,
                    "transparent_output_dbv": transparent,
                    "identification_output_dbv": identified,
                    "identification_attenuation_db": attenuation,
                    "inferred_fractional_index": index,
                    "detector_input_dbfs_peak": level_dbfs_peak,
                    "transparent_loop_delta_db": transparent - source,
                    "included": True,
                    "exclusion_reason": "",
                }
            )

    if len(rows) < MIN_INCLUDED_POINTS:
        raise SystemExit("Need at least eight complete calibration rows")

    median_loop_delta = statistics.median(
        float(row["transparent_loop_delta_db"]) for row in rows
    )
    for row in rows:
        deviation = abs(float(row["transparent_loop_delta_db"]) - median_loop_delta)
        if deviation > TRANSPARENT_DELTA_OUTLIER_DB:
            row["included"] = False
            row["exclusion_reason"] = (
                "transparent path differs from the session median by "
                f"{deviation:.3f} dB"
            )

    included = [row for row in rows if bool(row["included"])]
    excluded = [row for row in rows if not bool(row["included"])]
    if len(included) < MIN_INCLUDED_POINTS:
        raise SystemExit(
            f"Need at least {MIN_INCLUDED_POINTS} calibration rows after QC; "
            f"only {len(included)} remain"
        )

    xs = [float(row["detector_input_dbfs_peak"]) for row in included]
    ys = [float(row["inferred_fractional_index"]) for row in included]
    intercept, slope, r_squared = regression(xs, ys)

    coordinates = sorted(zip(ys, xs))
    if any(right[0] <= left[0] for left, right in zip(coordinates, coordinates[1:])):
        raise SystemExit("Measured detector indices are not strictly monotonic")
    if min(xs) > THRESHOLD_DBFS_PEAK or max(xs) < -1.856:
        raise SystemExit(
            "Calibration range does not bracket both CEC1 knee transitions: "
            f"{min(xs):.3f} to {max(xs):.3f} dBFS peak"
        )

    table_rows: list[dict[str, float | int | str]] = []
    words: list[bytes] = []
    for index in range(45):
        level = interpolate_with_endpoint_extrapolation(index, coordinates)
        gain_db, output = target_gain_db(level)
        linear = 10.0 ** (gain_db / 20.0)
        word = q523_word(linear)
        words.append(word)
        table_rows.append(
            {
                "index": index,
                "mapped_input_dbfs_peak": level,
                "target_output_dbfs_peak": output,
                "gain_db": gain_db,
                "linear_gain": linear,
                "q5_23_hex": "0x" + word.hex().upper(),
            }
        )

    nominal = NOMINAL_SCRIPT.read_text(encoding="utf-8")
    rendered_words = "\n".join(
        csharp_word(
            word,
            int(row["index"]),
            float(row["mapped_input_dbfs_peak"]),
            float(row["gain_db"]),
        )
        for word, row in zip(words, table_rows)
    )
    replacement = (
        "byte[][] targetWords = new byte[][] {\n"
        + rendered_words.rstrip(",")
        + "\n};"
    )
    calibrated, count = re.subn(
        r"byte\[\]\[\] targetWords = new byte\[\]\[\] \{.*?\n\};",
        replacement,
        nominal,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise SystemExit("Could not replace targetWords in nominal SigmaStudio script")
    calibrated = calibrated.replace(
        "// Apply the CEC1/openMHA-compatible output soft clip",
        "// Apply detector-calibrated CEC1/openMHA-compatible output soft clip",
        1,
    )
    calibrated, export_comment_count = re.subn(
        r"// Generated against tiresias-eval export at commit [0-9a-f]+\.",
        "// Detector coordinates calibrated from softclip_detector_calibration.csv.\n"
        "// The CEC1 curve is sampled on the measured monotonic, piecewise-linear "
        "detector map.\n"
        f"// {len(included)} points included; {len(excluded)} transparent-path "
        "outlier(s) excluded.",
        calibrated,
        count=1,
    )
    if export_comment_count != 1:
        raise SystemExit("Could not replace Sigma export provenance comment")
    calibrated = calibrated.replace(
        "// Each word is a linear gain in 5.23 format. Detector levels are\n"
        "// -90, -87, ..., +42 dBFS. The requested transfer is:",
        "// Each word is a linear gain in 5.23 format. Detector coordinates are\n"
        "// obtained from the independent electrical identification. The transfer is:",
        1,
    )
    CALIBRATED_SCRIPT.write_text(calibrated, encoding="utf-8")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULTS_DIR / "softclip_detector_fit.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (RESULTS_DIR / "softclip_calibrated_lut.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table_rows[0]))
        writer.writeheader()
        writer.writerows(table_rows)

    metadata = {
        "method": "independent SigmaDSP detector-index identification",
        "calibration_file": str(CALIBRATION_CSV.relative_to(ROOT)),
        "complete_points": len(rows),
        "included_points": len(included),
        "excluded_points": len(excluded),
        "transparent_loop_delta_median_db": median_loop_delta,
        "transparent_delta_outlier_threshold_db": TRANSPARENT_DELTA_OUTLIER_DB,
        "detector_input_range_dbfs_peak": [min(xs), max(xs)],
        "linear_fit_diagnostic_only": {
            "equation": "index = intercept + slope * detector_input_dbfs_peak",
            "intercept": intercept,
            "slope_index_per_db": slope,
            "r_squared": r_squared,
        },
        "resampling": {
            "method": "monotonic piecewise-linear interpolation",
            "endpoint_behavior": "linear extrapolation using nearest measured segment",
        },
        "excluded_rows": [
            {
                "source_input_dbv": row["source_input_dbv"],
                "transparent_output_dbv": row["transparent_output_dbv"],
                "identification_output_dbv": row["identification_output_dbv"],
                "reason": row["exclusion_reason"],
            }
            for row in excluded
        ],
        "cec1_curve": {
            "threshold_dbfs_peak": THRESHOLD_DBFS_PEAK,
            "compression_slope": COMPRESSION_SLOPE,
            "ceiling_dbfs_peak": CEILING_DBFS_PEAK,
        },
        "not_fitted_to_openmha_output": True,
    }
    (RESULTS_DIR / "softclip_calibration.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    report = (
        "# SigmaDSP SoftClip detector calibration\n\n"
        f"- Complete points: {len(rows)}\n"
        f"- Included after transparent-path QC: {len(included)}\n"
        f"- Excluded: {len(excluded)}\n"
        f"- Median transparent loop delta: {median_loop_delta:.3f} dB\n"
        f"- Detector range: {min(xs):.3f} to {max(xs):.3f} dBFS peak\n"
        "- LUT resampling: monotonic piecewise-linear measured detector map\n"
        f"- Linear-fit diagnostic only: R² = {r_squared:.9f}\n"
        "- The fit uses only transparent/identification measurements; openMHA output "
        "is not an optimization target.\n\n"
        + (
            "## Excluded raw rows\n\n"
            + "\n".join(
                f"- Source {float(row['source_input_dbv']):.2f} dBV: "
                f"transparent {float(row['transparent_output_dbv']):.2f} dBV; "
                f"{row['exclusion_reason']}."
                for row in excluded
            )
            + "\n\n"
            if excluded
            else ""
        )
        + f"Generated script: `{CALIBRATED_SCRIPT.relative_to(ROOT)}`\n"
    )
    (RESULTS_DIR / "SOFTCLIP_CALIBRATION_RESULT.md").write_text(
        report, encoding="utf-8"
    )
    print(
        f"PASS: {len(included)}/{len(rows)} points included, "
        f"linear diagnostic R^2={r_squared:.9f}"
    )
    print(f"Generated {CALIBRATED_SCRIPT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
