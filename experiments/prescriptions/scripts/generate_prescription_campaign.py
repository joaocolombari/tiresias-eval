#!/usr/bin/env python3
"""Prepare the REW campaign and stationary Sigma response predictions."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_sigma_adau1787_prescription import (  # noqa: E402
    detector_from_equivalent_spl,
    interpolate_linear_gain_from_lut,
)
from generate_sigma_detector_identification import (  # noqa: E402
    export_modules,
    filterbank_contributions,
)


CONFIG_PATH = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "config"
    / "prescription_campaign_2026-08-14.json"
)
PRESCRIPTION_CONFIG_PATH = (
    WORKSPACE / "tiresias-eval-sigma" / "config" / "prescription_eval.json"
)
CALIBRATION_PATH = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "config"
    / "detector_calibration_eval.json"
)
GENERATED = WORKSPACE / "tiresias-eval-sigma" / "scripts" / "generated"
CAMPAIGN = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_profile(profile: str) -> None:
    profile_dir = GENERATED / profile
    required = [
        profile_dir / f"{profile}_apply_prescription.sss",
        profile_dir / f"{profile}_restore_unity.sss",
        profile_dir / f"{profile}_manifest.json",
        profile_dir / f"{profile}_validation_targets.csv",
        profile_dir / "SHA256SUMS.txt",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing {profile} artifacts: {missing}")
    expected = {}
    for line in required[-1].read_text(encoding="utf-8").splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[filename.strip()] = digest
    for path in required[:-1]:
        actual = sha256(path)
        if expected.get(path.name) != actual:
            raise RuntimeError(f"Checksum mismatch: {path}")


def profile_context(
    profile: str,
    calibration: dict,
    modules: list[dict],
    centres: tuple[float, ...],
) -> dict:
    manifest = load_json(GENERATED / profile / f"{profile}_manifest.json")
    reference_magnitudes = []
    for index, centre in enumerate(centres):
        contributions, _ = filterbank_contributions(modules, centre, 48000.0)
        reference_magnitudes.append(abs(contributions[index]))
    return {
        "modules": modules,
        "calibration": calibration["measured_band_calibration"],
        "detector_points": [
            float(value) for value in manifest["mapping"]["detector_points_dbfs"]
        ],
        "tables": [row["quantized_lut_gain_db"] for row in manifest["tables"]],
        "bias_db": float(manifest["mapping"]["quantized_bias_total_db"]),
        "reference_magnitudes": reference_magnitudes,
    }


def predicted_gain(
    frequency: float,
    level: float,
    context: dict,
) -> float:
    contributions, unity_response = filterbank_contributions(
        context["modules"], frequency, 48000.0
    )
    active_sum = 0.0 + 0.0j
    for index in range(8):
        calibration = context["calibration"][f"B{index + 1}"]
        detector = detector_from_equivalent_spl(level, calibration)
        ratio = abs(contributions[index]) / context["reference_magnitudes"][index]
        detector += 20.0 * math.log10(max(ratio, 1e-30))
        if calibration.get("low_level_floor_detected"):
            detector = max(detector, float(calibration["detector_dbfs"][0]))
        gain_db = interpolate_linear_gain_from_lut(
            detector,
            context["detector_points"],
            context["tables"][index],
        )
        active_sum += contributions[index] * 10.0 ** (gain_db / 20.0)
    response = (
        active_sum * 10.0 ** (context["bias_db"] / 20.0)
        + contributions[8]
    )
    return 20.0 * math.log10(abs(response / unity_response))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    campaign = load_json(CONFIG_PATH)
    prescription_config = load_json(PRESCRIPTION_CONFIG_PATH)
    calibration = load_json(CALIBRATION_PATH)
    export_path = (
        PRESCRIPTION_CONFIG_PATH.parent / prescription_config["sigma_export_xml"]
    ).resolve()
    modules = export_modules(export_path)
    centres = tuple(
        float(value)
        for value in load_json(
            WORKSPACE
            / "experiments"
            / "prescriptions"
            / "generated"
            / "prescriptions"
            / "N1.json"
        )["filterbank"]["centres_hz"][:8]
    )
    profiles = [str(value) for value in campaign["profiles"]]
    levels = [float(value) for value in campaign["levels_db_spl"]]
    dac_levels = [float(value) for value in campaign["rew_dac_levels_dbv"]]
    if len(levels) != len(dac_levels):
        raise ValueError("Level and DAC grids must have equal lengths")

    for profile in profiles:
        verify_profile(profile)
        (CAMPAIGN / "raw" / profile).mkdir(parents=True, exist_ok=True)
    (CAMPAIGN / "raw" / "unity").mkdir(parents=True, exist_ok=True)
    for name in ("processed", "figures", "reports", "expected/sigma", "expected/openmha"):
        (CAMPAIGN / name).mkdir(parents=True, exist_ok=True)

    manifest_path = CAMPAIGN / "CAMPAIGN_MEASUREMENT_MANIFEST.csv"
    preserved_fields: dict[str, dict[str, str]] = {}
    if manifest_path.is_file():
        with manifest_path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                preserved_fields[row["text_path"]] = {
                    key: row.get(key, "")
                    for key in ("acquired", "script_pass", "clip_warning", "notes")
                }

    manifest_rows = []
    sequence = 1
    for level, dac in zip(levels, dac_levels):
        level_tag = int(level)
        dac_tag = f"{abs(dac):.2f}".replace(".", "p")
        stem = f"unity_{level_tag}dBSPL_-{dac_tag}dBV"
        manifest_row = {
            "sequence": sequence,
            "state": "unity",
            "profile": "unity",
            "level_db_spl": f"{level:.0f}",
            "rew_dac_dbv": f"{dac:.2f}",
            "rew_measurement_name": stem,
            "mdat_path": f"raw/unity/{stem}.mdat",
            "text_path": f"raw/unity/{stem}.txt",
            "acquired": "",
            "script_pass": "not_applicable",
            "clip_warning": "",
            "notes": "",
        }
        for key, value in preserved_fields.get(manifest_row["text_path"], {}).items():
            if key != "script_pass" or value:
                manifest_row[key] = value
        manifest_rows.append(manifest_row)
        sequence += 1
    for profile in profiles:
        for level, dac in zip(levels, dac_levels):
            level_tag = int(level)
            dac_tag = f"{abs(dac):.2f}".replace(".", "p")
            stem = f"{profile}_{level_tag}dBSPL_-{dac_tag}dBV"
            manifest_row = {
                "sequence": sequence,
                "state": "prescription",
                "profile": profile,
                "level_db_spl": f"{level:.0f}",
                "rew_dac_dbv": f"{dac:.2f}",
                "rew_measurement_name": stem,
                "mdat_path": f"raw/{profile}/{stem}.mdat",
                "text_path": f"raw/{profile}/{stem}.txt",
                "acquired": "",
                "script_pass": "",
                "clip_warning": "",
                "notes": "",
            }
            manifest_row.update(preserved_fields.get(manifest_row["text_path"], {}))
            manifest_rows.append(manifest_row)
            sequence += 1
    write_csv(manifest_path, manifest_rows)

    frequency_grid = np.geomspace(100.0, 10000.0, 481)
    expected_rows = []
    headroom_rows = []
    attenuation_db = float(campaign["output_headroom"]["attenuation_db"])
    for profile in profiles:
        context = profile_context(profile, calibration, modules, centres)
        profile_rows = []
        for level in levels:
            level_rows = []
            for frequency in frequency_grid:
                gain_db = predicted_gain(float(frequency), level, context)
                row = {
                    "profile": profile,
                    "level_db_spl": f"{level:.0f}",
                    "frequency_hz": f"{frequency:.9f}",
                    "sigma_expected_recombined_gain_db": f"{gain_db:.9f}",
                    "model": "measured detector maps + quantized Sigma LUTs + complex LR4 recombination",
                }
                profile_rows.append(row)
                expected_rows.append(row)
                level_rows.append((float(frequency), gain_db))
            maximum_frequency, maximum_gain = max(level_rows, key=lambda item: item[1])
            dac = dac_levels[levels.index(level)]
            output_without_attenuation = dac + maximum_gain
            output_with_attenuation = output_without_attenuation + attenuation_db
            headroom_rows.append({
                "profile": profile,
                "level_db_spl": f"{level:.0f}",
                "rew_dac_dbv": f"{dac:.2f}",
                "maximum_expected_gain_db": f"{maximum_gain:.6f}",
                "frequency_of_maximum_hz": f"{maximum_frequency:.6f}",
                "predicted_max_output_without_attenuation_dbv": f"{output_without_attenuation:.6f}",
                "output_headroom_db": f"{attenuation_db:.3f}",
                "predicted_max_output_with_attenuation_dbv": f"{output_with_attenuation:.6f}",
                "margin_to_scarlett_1vrms_fs_db": f"{-output_with_attenuation:.6f}",
                "status": "PASS" if output_with_attenuation <= -6.0 else "NO_GO",
            })
        write_csv(
            CAMPAIGN / "expected" / "sigma" / f"{profile}_sigma_expected.csv",
            profile_rows,
        )
    write_csv(
        CAMPAIGN / "expected" / "sigma" / "sigma_expected_all_profiles.csv",
        expected_rows,
    )
    write_csv(CAMPAIGN / "CAMPAIGN_HEADROOM_AUDIT.csv", headroom_rows)
    failed_headroom = [row for row in headroom_rows if row["status"] != "PASS"]
    if failed_headroom:
        raise RuntimeError(
            "Output headroom is below 6 dB for: "
            + ", ".join(
                f"{row['profile']}@{row['level_db_spl']}dBSPL"
                for row in failed_headroom
            )
        )

    metadata = {
        "campaign_config": str(CONFIG_PATH.relative_to(WORKSPACE)),
        "campaign_config_sha256": sha256(CONFIG_PATH),
        "prescription_config_sha256": sha256(PRESCRIPTION_CONFIG_PATH),
        "detector_calibration_sha256": sha256(CALIBRATION_PATH),
        "sigma_export_sha256": sha256(export_path),
        "profiles": profiles,
        "levels_db_spl": levels,
        "frequency_grid_points": len(frequency_grid),
        "frequency_grid_hz": [float(frequency_grid[0]), float(frequency_grid[-1])],
        "measurement_count": len(manifest_rows),
        "unity_measurement_count": len(levels),
        "prescription_measurement_count": len(profiles) * len(levels),
        "headroom_audit": "CAMPAIGN_HEADROOM_AUDIT.csv",
        "minimum_predicted_margin_to_scarlett_fs_db": min(
            float(row["margin_to_scarlett_1vrms_fs_db"])
            for row in headroom_rows
        ),
    }
    (CAMPAIGN / "CAMPAIGN_GENERATION.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Prepared {len(profiles)} profiles, {len(manifest_rows)} REW measurements "
        f"and {len(expected_rows)} Sigma prediction points in {CAMPAIGN}"
    )


if __name__ == "__main__":
    main()
