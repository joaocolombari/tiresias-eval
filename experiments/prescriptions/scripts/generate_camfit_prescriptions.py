#!/usr/bin/env python3
"""Generate CAMFIT/OpenMHA prescriptions for the ten Bisgaard audiograms."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from clarity.enhancer.gha.gha_interface import GHAHearingAid
from clarity.enhancer.gha.gha_utils import format_gaintable, get_gaintable
from clarity.utils.audiogram import Audiogram


WORKSPACE = Path(__file__).resolve().parents[3]
EXPERIMENT = WORKSPACE / "experiments" / "prescriptions"
CLARITY_SOURCE = WORKSPACE / "tools" / "clarity" / "source"
CLARITY_COMMIT = "9df6486fb0bddc7619b3b99f1b3a5c72c109a3ec"
PROFILE_ORDER = ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "S1", "S2", "S3"]
EARS = ["left", "right"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_audiograms(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            frequencies = []
            levels = []
            for key, value in row.items():
                if key.startswith("hl_"):
                    frequencies.append(float(key.removeprefix("hl_")))
                    levels.append(float(value))
            result[row["profile"]] = {
                "category": row["category"],
                "frequencies_hz": frequencies,
                "levels_db_hl": levels,
            }
    if list(result) != PROFILE_ORDER:
        raise ValueError(f"Unexpected Bisgaard profile order: {list(result)}")
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def rounded(values: np.ndarray, digits: int = 6) -> list[Any]:
    return np.round(values.astype(float), digits).tolist()


def value_at(levels: np.ndarray, values: np.ndarray, level: float) -> float:
    return float(np.interp(level, levels, values))


def simplify_curve_indices(
    x: np.ndarray,
    y: np.ndarray,
    tolerance_db: float,
) -> list[int]:
    """Return compact graph knots within a vertical-error tolerance.

    SigmaStudio linearly interpolates between control points in its dB-domain
    compressor graph. The CAMFIT curves are already piecewise linear in that
    same domain, so retaining the points with the largest vertical error gives
    a compact, directly enterable representation.
    """
    if x.ndim != 1 or y.ndim != 1 or x.size != y.size or x.size < 2:
        raise ValueError("Curve simplification requires equal 1-D arrays")

    retained = {0, x.size - 1}
    pending = [(0, x.size - 1)]
    while pending:
        start, end = pending.pop()
        if end <= start + 1:
            continue
        interpolated = np.interp(x[start + 1 : end], x[[start, end]], y[[start, end]])
        errors = np.abs(y[start + 1 : end] - interpolated)
        relative_index = int(np.argmax(errors))
        maximum_error = float(errors[relative_index])
        if maximum_error > tolerance_db:
            split = start + 1 + relative_index
            retained.add(split)
            pending.extend([(start, split), (split, end)])

    return sorted(retained)


def derive_compression_ratio(
    levels: np.ndarray,
    uncorrected_gain: np.ndarray,
    maximum_output: float,
) -> float | None:
    """Recover the constant CAMFIT ratio before output limiting.

    The full gain table is authoritative. This derived scalar is only a compact
    aid for implementing a conventional SigmaStudio compressor.
    """
    output = levels + uncorrected_gain
    if float(np.max(uncorrected_gain)) <= 0.01:
        return 1.0
    delta_output = np.diff(output)
    valid = (
        (output[:-1] < maximum_output - 1.0)
        & (output[1:] < maximum_output - 0.1)
        & (uncorrected_gain[:-1] > 0.01)
        & (delta_output > 0.01)
        & (delta_output <= 1.001)
    )
    slopes = delta_output[valid]
    if not slopes.size:
        return None
    slope = float(np.median(slopes))
    return 1.0 / slope


def generate_openmha_configs(
    output_dir: Path,
    profile: str,
    formatted_gain_table: str,
    settings: dict[str, Any],
) -> None:
    template = CLARITY_SOURCE / settings["openmha_template"]
    gha = GHAHearingAid(
        sample_rate=settings["sample_rate_hz"],
        ahr=settings["amplification_headroom_db"],
        cfg_file="prerelease_combination4_smooth",
        noise_gate_levels=settings["noise_gate_levels_db_spl"],
        noise_gate_slope=settings["noise_gate_slope"],
        cr_level=settings["compression_ratio_reference_level_db_spl"],
        max_output_level=settings["maximum_output_db_spl"],
        equiv_0db_spl=settings["equivalent_0_dbfs_db_spl"],
    )
    text = gha.create_configured_cfgfile(
        input_file=f"inputs/{profile}_4ch.wav",
        output_file=f"outputs/{profile}_openmha.wav",
        formatted_sGt=formatted_gain_table,
        cfg_template_file=template,
    )

    exact_dir = output_dir / "openmha_cfg" / "cec1_exact"
    exact_dir.mkdir(parents=True, exist_ok=True)
    (exact_dir / f"{profile}.cfg").write_text(text, encoding="utf-8")

    one_mic_text = text.replace(
        "mha.mhachain.adm.bypass = 0",
        f"mha.mhachain.adm.bypass = {settings['openmha_adm_bypass_for_one_mic_tests']}",
    )
    if one_mic_text == text:
        raise RuntimeError("Could not set ADM bypass in generated openMHA configuration")
    one_mic_dir = output_dir / "openmha_cfg" / "one_mic_reference"
    one_mic_dir.mkdir(parents=True, exist_ok=True)
    (one_mic_dir / f"{profile}.cfg").write_text(one_mic_text, encoding="utf-8")


def write_manifest(root: Path) -> None:
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        is_smoke_artifact = (
            relative.parts[0] in {"inputs", "outputs"}
            or path.name.startswith("openmha_smoke_")
        )
        is_tool_sidecar = path.name.endswith(".inspect.ndjson")
        if (
            path.is_file()
            and path.name != "SHA256SUMS.txt"
            and not is_smoke_artifact
            and not is_tool_sidecar
        ):
            rows.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}"
            )
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=EXPERIMENT / "generated")
    args = parser.parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = load_json(EXPERIMENT / "config" / "camfit_cec1.json")
    profiles = load_audiograms(EXPERIMENT / "data" / "bisgaard_2010_audiograms.csv")
    filter_centres = np.asarray(settings["filterbank_centres_hz"], dtype=float)
    filter_edges = np.asarray(settings["filterbank_edges_hz"], dtype=float)
    input_levels = np.arange(
        settings["gain_table_minimum_input_db_spl"],
        settings["gain_table_maximum_input_db_spl"] + settings["gain_table_step_db"],
        settings["gain_table_step_db"],
        dtype=float,
    )
    if input_levels.size != 121:
        raise ValueError("The CEC1 gain table must have 121 input-level points")

    long_rows: list[dict[str, Any]] = []
    sigma_rows: list[dict[str, Any]] = []
    sigma_full_rows: list[dict[str, Any]] = []
    sigma_ui_rows: list[dict[str, Any]] = []
    listeners: dict[str, Any] = {}
    summary: dict[str, Any] = {
        "source": {
            "bisgaard_doi": "10.1177/1084713810379609",
            "clarity_repository": "https://github.com/claritychallenge/clarity",
            "clarity_commit": CLARITY_COMMIT,
        },
        "settings": settings,
        "profiles": {},
    }

    for profile in PROFILE_ORDER:
        profile_data = profiles[profile]
        frequencies = np.asarray(profile_data["frequencies_hz"], dtype=float)
        hearing_loss = np.asarray(profile_data["levels_db_hl"], dtype=float)
        audiogram = Audiogram(levels=hearing_loss, frequencies=frequencies)

        gain_table = get_gaintable(
            audiogram_left=audiogram,
            audiogram_right=audiogram,
            noisegate_levels=np.asarray(settings["noise_gate_levels_db_spl"], dtype=float),
            noisegate_slope=float(settings["noise_gate_slope"]),
            cr_level=float(settings["compression_ratio_reference_level_db_spl"]),
            max_output_level=float(settings["maximum_output_db_spl"]),
        )
        corrected = np.asarray(gain_table["sGt"], dtype=float).copy()
        uncorrected = np.asarray(gain_table["sGt_uncorr"], dtype=float)
        corrected[[8, 17], :] = 0.0

        if corrected.shape != (18, 121) or uncorrected.shape != (121, 9, 2):
            raise RuntimeError(f"Unexpected gain-table shape for {profile}")
        if not np.allclose(corrected[:9], corrected[9:]):
            raise RuntimeError(f"Symmetric audiogram produced asymmetric gains for {profile}")
        active_rows = np.r_[0:8, 9:17]
        if (
            np.max(input_levels[None, :] + corrected[active_rows])
            > settings["maximum_output_db_spl"] + 1e-6
        ):
            raise RuntimeError(f"Output limit exceeded for {profile}")
        if not np.all(np.diff(input_levels[None, :] + corrected, axis=1) >= -1e-6):
            raise RuntimeError(f"Non-monotonic input/output map for {profile}")

        format_source = copy.deepcopy(gain_table)
        formatted = format_gaintable(format_source, noisegate_corr=True)
        generate_openmha_configs(output_dir, profile, formatted, settings)

        listeners[f"BIS_{profile}"] = {
            "name": f"BIS_{profile}",
            "audiogram_cfs": rounded(frequencies),
            "audiogram_levels_l": rounded(hearing_loss),
            "audiogram_levels_r": rounded(hearing_loss),
        }

        profile_json: dict[str, Any] = {
            "profile": profile,
            "category": profile_data["category"],
            "audiogram": {
                "frequencies_hz": rounded(frequencies),
                "hearing_loss_db_hl_left": rounded(hearing_loss),
                "hearing_loss_db_hl_right": rounded(hearing_loss),
                "endpoint_policy": settings["audiogram_endpoint_policy"],
            },
            "filterbank": {
                "centres_hz": rounded(filter_centres),
                "edges_hz": rounded(filter_edges),
                "highest_band_gain_is_forced_to_zero_db": True,
            },
            "dynamics": {
                "input_levels_db_spl": rounded(input_levels),
                "gain_db_left_band_by_level": rounded(corrected[:9]),
                "gain_db_right_band_by_level": rounded(corrected[9:]),
                "attack_time_ms": settings["attack_time_ms"],
                "release_time_ms": settings["release_time_ms"],
                "rms_level_time_constant_ms": settings["rms_level_time_constant_ms"],
            },
        }
        profile_dir = output_dir / "prescriptions"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / f"{profile}.json").write_text(
            json.dumps(profile_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        for ear_index, ear in enumerate(EARS):
            for band_index, centre_hz in enumerate(filter_centres):
                row_index = ear_index * 9 + band_index
                gain_curve = corrected[row_index]
                raw_curve = uncorrected[:, band_index, ear_index]
                output_curve = input_levels + gain_curve
                ratio = derive_compression_ratio(
                    input_levels, raw_curve, settings["maximum_output_db_spl"]
                )
                limiter_hits = input_levels[output_curve >= settings["maximum_output_db_spl"] - 1e-6]
                limiter_input = float(limiter_hits[0]) if limiter_hits.size else math.nan
                active = band_index < 8
                if not active:
                    ratio = None
                    limiter_input = math.nan

                sigma_rows.append(
                    {
                        "profile": profile,
                        "ear": ear,
                        "band": band_index + 1,
                        "active_prescription": active,
                        "edge_low_hz": f"{filter_edges[band_index]:.4f}",
                        "edge_high_hz": f"{filter_edges[band_index + 1]:.4f}",
                        "centre_hz": f"{centre_hz:.4f}",
                        "noise_gate_knee_db_spl": settings["noise_gate_levels_db_spl"][band_index],
                        "camfit_compression_ratio": "" if ratio is None else f"{ratio:.6f}",
                        "gain_at_45_db_spl": f"{value_at(input_levels, gain_curve, 45):.6f}",
                        "gain_at_65_db_spl": f"{value_at(input_levels, gain_curve, 65):.6f}",
                        "gain_at_85_db_spl": f"{value_at(input_levels, gain_curve, 85):.6f}",
                        "limiter_input_knee_db_spl": "" if math.isnan(limiter_input) else f"{limiter_input:.1f}",
                        "maximum_output_db_spl": settings["maximum_output_db_spl"],
                        "attack_ms": settings["attack_time_ms"],
                        "release_ms": settings["release_time_ms"],
                        "rms_level_time_constant_ms": settings["rms_level_time_constant_ms"],
                        "implementation_note": "CAMFIT table" if active else "unity passthrough; boundary band",
                    }
                )

                for input_level, gain_db, output_level in zip(
                    input_levels, gain_curve, output_curve
                ):
                    long_rows.append(
                        {
                            "profile": profile,
                            "ear": ear,
                            "band": band_index + 1,
                            "centre_hz": f"{centre_hz:.4f}",
                            "edge_low_hz": f"{filter_edges[band_index]:.4f}",
                            "edge_high_hz": f"{filter_edges[band_index + 1]:.4f}",
                            "input_level_db_spl": f"{input_level:.1f}",
                            "gain_db": f"{gain_db:.6f}",
                            "output_level_db_spl": f"{output_level:.6f}",
                        }
                    )

                input_peaklevel = float(settings["equivalent_0_dbfs_db_spl"])
                output_peaklevel = input_peaklevel + float(
                    settings["amplification_headroom_db"]
                )
                sigma_input = input_levels - input_peaklevel
                # Keep prescription gain inside each band compressor. Apply the
                # calibration/headroom difference once, after band recombination.
                sigma_graph_output = sigma_input + gain_curve
                sigma_final_output = output_curve - output_peaklevel
                graph_minimum = float(settings["sigma_graph_minimum_input_dbfs"])
                graph_maximum = float(settings["sigma_graph_maximum_input_dbfs"])
                in_graph_range = (sigma_input >= graph_minimum) & (
                    sigma_input <= graph_maximum
                )

                for level_index in range(input_levels.size):
                    sigma_full_rows.append(
                        {
                            "profile": profile,
                            "ear": ear,
                            "band": band_index + 1,
                            "active_prescription": active,
                            "centre_hz": f"{centre_hz:.4f}",
                            "edge_low_hz": f"{filter_edges[band_index]:.4f}",
                            "edge_high_hz": f"{filter_edges[band_index + 1]:.4f}",
                            "input_level_db_spl": f"{input_levels[level_index]:.1f}",
                            "camfit_gain_db": f"{gain_curve[level_index]:.6f}",
                            "output_level_db_spl": f"{output_curve[level_index]:.6f}",
                            "sigma_graph_input_dbfs": f"{sigma_input[level_index]:.6f}",
                            "sigma_graph_output_dbfs": f"{sigma_graph_output[level_index]:.6f}",
                            "sigma_output_after_global_headroom_dbfs": (
                                f"{sigma_final_output[level_index]:.6f}"
                            ),
                            "global_headroom_gain_db": f"{input_peaklevel - output_peaklevel:.6f}",
                            "within_configured_sigma_graph_range": bool(
                                in_graph_range[level_index]
                            ),
                        }
                    )

                graph_indices = np.flatnonzero(in_graph_range)
                compact_local_indices = simplify_curve_indices(
                    sigma_input[graph_indices],
                    sigma_graph_output[graph_indices],
                    float(settings["sigma_curve_tolerance_db"]),
                )
                compact_indices = graph_indices[compact_local_indices]
                reconstructed = np.interp(
                    sigma_input[graph_indices],
                    sigma_input[compact_indices],
                    sigma_graph_output[compact_indices],
                )
                compact_error = float(
                    np.max(
                        np.abs(
                            sigma_graph_output[graph_indices] - reconstructed
                        )
                    )
                )
                if compact_error > float(settings["sigma_curve_tolerance_db"]) + 1e-9:
                    raise RuntimeError(
                        f"Sigma curve simplification exceeded tolerance for "
                        f"{profile} {ear} band {band_index + 1}: {compact_error} dB"
                    )

                for point_index, level_index in enumerate(compact_indices, start=1):
                    sigma_ui_rows.append(
                        {
                            "profile": profile,
                            "ear": ear,
                            "band": band_index + 1,
                            "active_prescription": active,
                            "point": point_index,
                            "centre_hz": f"{centre_hz:.4f}",
                            "input_level_db_spl": f"{input_levels[level_index]:.1f}",
                            "sigma_graph_input_dbfs": f"{sigma_input[level_index]:.6f}",
                            "sigma_graph_output_dbfs": f"{sigma_graph_output[level_index]:.6f}",
                            "camfit_gain_db": f"{gain_curve[level_index]:.6f}",
                            "sigma_output_after_global_headroom_dbfs": (
                                f"{sigma_final_output[level_index]:.6f}"
                            ),
                            "maximum_interpolation_error_db": f"{compact_error:.9f}",
                            "implementation_note": (
                                "enter x/y in compressor graph"
                                if active
                                else "bypass compressor; global headroom still applies"
                            ),
                        }
                    )

        summary["profiles"][profile] = {
            "category": profile_data["category"],
            "maximum_gain_db": round(float(np.max(corrected)), 6),
            "minimum_gain_db": round(float(np.min(corrected)), 6),
        }

    write_csv(output_dir / "gain_table_long.csv", long_rows)
    write_csv(output_dir / "sigma_compact_targets.csv", sigma_rows)
    write_csv(output_dir / "sigma_compressor_curve_full.csv", sigma_full_rows)
    write_csv(output_dir / "sigma_compressor_curve_ui.csv", sigma_ui_rows)
    (output_dir / "listeners_bisgaard_symmetric.json").write_text(
        json.dumps(listeners, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "generation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_manifest(output_dir)
    print(f"Generated {len(PROFILE_ORDER)} prescriptions in {output_dir}")
    print(f"Full table rows: {len(long_rows)}")
    print(f"Compact Sigma rows: {len(sigma_rows)}")
    print(f"Full Sigma curve rows: {len(sigma_full_rows)}")
    print(f"SigmaStudio UI points: {len(sigma_ui_rows)}")


if __name__ == "__main__":
    main()
