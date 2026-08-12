#!/usr/bin/env python3
"""Generate safe SigmaStudio scripts for an ADAU1787 CAMFIT prescription."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = (
    WORKSPACE / "tiresias-eval-sigma" / "config" / "n1_initial_validation.json"
)
UNITY_WORD = bytes.fromhex("00800000")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_from(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interpolate(x: float, xp: list[float], fp: list[float]) -> float:
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    lower = int(math.floor(x - xp[0]))
    lower = max(0, min(lower, len(xp) - 2))
    while xp[lower + 1] < x:
        lower += 1
    span = xp[lower + 1] - xp[lower]
    fraction = (x - xp[lower]) / span
    return fp[lower] + fraction * (fp[lower + 1] - fp[lower])


def fixed_5_23_from_db(gain_db: float) -> tuple[float, int, bytes]:
    linear = 10.0 ** (gain_db / 20.0)
    if not 0.0 <= linear < 16.0:
        raise ValueError(f"Gain {gain_db:.6f} dB is outside positive 5.23 range")
    integer = int(round(linear * (1 << 23)))
    if integer >= 0x08000000:
        raise ValueError(f"Encoded gain {gain_db:.6f} dB exceeds 5.23 positive maximum")
    return linear, integer, integer.to_bytes(4, byteorder="big", signed=False)


def interpolate_linear_gain_from_lut(
    detector_dbfs: float,
    detector_points: list[float],
    gain_db: list[float],
) -> float:
    unique_points = detector_points[1:]
    unique_gains = gain_db[1:]
    if detector_dbfs <= unique_points[0]:
        return unique_gains[0]
    if detector_dbfs >= unique_points[-1]:
        return unique_gains[-1]
    right = next(i for i, value in enumerate(unique_points) if value >= detector_dbfs)
    if unique_points[right] == detector_dbfs:
        return unique_gains[right]
    left = right - 1
    fraction = (
        (detector_dbfs - unique_points[left])
        / (unique_points[right] - unique_points[left])
    )
    gain_linear = (
        (1.0 - fraction) * 10.0 ** (unique_gains[left] / 20.0)
        + fraction * 10.0 ** (unique_gains[right] / 20.0)
    )
    return 20.0 * math.log10(gain_linear)


def calibrate_b1_three_checkpoints(
    detector_points: list[float],
    nominal_gain_db: list[float],
    calibration: dict[str, Any],
    levels: list[float],
    b1_camfit_gain: list[float],
) -> tuple[list[float], dict[str, Any]]:
    """Fit the coarse 3 dB LUT to three measured detector checkpoints.

    The ADAU block interpolates linear gain between fixed detector knots. The
    first two measured checkpoints fall in adjacent intervals, so solving the
    shared knot in linear gain gives an exact three-point bench validation.
    """
    detector = [float(x) for x in calibration["detector_dbfs"]]
    equivalent = [float(x) for x in calibration["equivalent_input_level_db_spl"]]
    if len(detector) != 3 or len(equivalent) != 3 or detector != sorted(detector):
        raise ValueError("B1 initial calibration requires three ordered checkpoints")
    target_db = [interpolate(level, levels, b1_camfit_gain) for level in equivalent]
    target_linear = [10.0 ** (gain / 20.0) for gain in target_db]

    grid = [float(x) for x in detector_points[1:]]
    values = [10.0 ** (gain / 20.0) for gain in nominal_gain_db[1:]]

    def bracket(value: float) -> tuple[int, int, float]:
        right = next(i for i, point in enumerate(grid) if point >= value)
        if grid[right] == value:
            return right, right, 0.0
        left = right - 1
        fraction = (value - grid[left]) / (grid[right] - grid[left])
        return left, right, fraction

    left0, right0, _ = bracket(detector[0])
    left1, right1, fraction1 = bracket(detector[1])
    left2, right2, _ = bracket(detector[2])
    if right0 != left1 or left1 == right1:
        raise ValueError("First two detector checkpoints must occupy adjacent LUT intervals")

    for index in range(0, right0 + 1):
        values[index] = target_linear[0]
    values[right0] = target_linear[0]
    values[right1] = (
        target_linear[1] - (1.0 - fraction1) * values[left1]
    ) / fraction1
    if values[right1] <= 0.0:
        raise ValueError("Three-point detector fit requires a non-positive LUT gain")
    values[left2] = target_linear[2]
    values[right2] = target_linear[2]

    fitted_db_unique = [20.0 * math.log10(value) for value in values]
    fitted_db = [fitted_db_unique[0], *fitted_db_unique]
    achieved_db = [
        interpolate_linear_gain_from_lut(value, detector_points, fitted_db)
        for value in detector
    ]
    errors = [got - wanted for got, wanted in zip(achieved_db, target_db)]
    return fitted_db, {
        "method": "three measured checkpoints; linear-gain interpolation on fixed 3 dB LUT grid",
        "detector_dbfs": detector,
        "equivalent_input_level_db_spl": equivalent,
        "target_gain_db": target_db,
        "achieved_unquantized_gain_db": achieved_db,
        "unquantized_error_db": errors,
        "maximum_unquantized_abs_error_db": max(abs(value) for value in errors),
        "limitation": "Initial B1 validation fit; behavior below 45 dB SPL is held and the interval between checkpoints is not a full detector transfer-function model.",
    }


def export_parameters(export_xml: Path) -> dict[str, list[dict[str, Any]]]:
    root = ET.parse(export_xml).getroot()
    result: dict[str, list[dict[str, Any]]] = {}
    for module in root.findall(".//Module"):
        cell = module.findtext("CellName")
        if not cell:
            continue
        parameters = []
        for item in module.findall(".//ModuleParameter"):
            parameters.append(
                {
                    "name": item.findtext("Name", ""),
                    "address": int(item.findtext("Address", "-1")),
                    "size": int(item.findtext("Size", "0")),
                    "data": item.findtext("Data", ""),
                }
            )
        result[cell] = parameters
    return result


def find_lut_address(parameters: dict[str, list[dict[str, Any]]], cell: str) -> int:
    candidates = [
        item for item in parameters[cell]
        if item["size"] == 136 and item["name"].lower().endswith("tab")
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected one 136-byte LUT for {cell}, found {candidates}")
    return int(candidates[0]["address"])


def find_gain_address(parameters: dict[str, list[dict[str, Any]]], cell: str) -> int:
    candidates = [item for item in parameters[cell] if item["size"] == 4]
    if len(candidates) != 1:
        raise ValueError(f"Expected one gain parameter for {cell}, found {candidates}")
    return int(candidates[0]["address"])


def csharp_bytes(data: bytes) -> str:
    return "new byte[] { " + ", ".join(f"0x{x:02X}" for x in data) + " }"


def csharp_ints(values: list[int]) -> str:
    return "new int[] { " + ", ".join(f"0x{x:04X}" for x in values) + " }"


def render_apply(
    profile: str,
    table_addresses: list[int],
    bias_addresses: list[int],
    table_data: list[bytes],
    bias_word: bytes,
    guard_word: bytes,
    bias_stage_db: float,
) -> str:
    tables = ",\n    ".join(csharp_bytes(data) for data in table_data)
    return f'''// #LANGUAGE# C#
// Generated prescription: {profile}. Run only after Link Compile Download.
// Writes every LUT as 34 independent four-byte transfers and verifies readback.

string icName = "IC 1";
string stage = "initialization";
int tableWords = 34;
int[] tableAddresses = {csharp_ints(table_addresses)};
int[] biasAddresses = {csharp_ints(bias_addresses)};
byte[] unityWord = {csharp_bytes(UNITY_WORD)};
byte[] guardWord = {csharp_bytes(guard_word)};
byte[] biasWord = {csharp_bytes(bias_word)};
byte[][] profileTables = new byte[][] {{
    {tables}
}};

try
{{
    // Strict pre-flight: saved project must be completely in unity.
    for (int band = 0; band < tableAddresses.Length; band++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[band] + 4 * wordIndex;
            byte[] actual = new byte[4];
            stage = System.String.Format("pre-flight B{{0}} word {{1}}", band + 1, wordIndex);
            ss.ICRegisterRead(icName, address, 4, ref actual);
            for (int k = 0; k < 4; k++)
                if (actual[k] != unityWord[k])
                    throw new System.OperationCanceledException(
                        System.String.Format("B{{0}} is not unity at 0x{{1:X4}}", band + 1, address + k));
        }}
    }}
    for (int gainIndex = 0; gainIndex < biasAddresses.Length; gainIndex++)
    {{
        byte[] actual = new byte[4];
        stage = System.String.Format("pre-flight bias {{0}}", gainIndex + 1);
        ss.ICRegisterRead(icName, biasAddresses[gainIndex], 4, ref actual);
        for (int k = 0; k < 4; k++)
            if (actual[k] != unityWord[k])
                throw new System.OperationCanceledException(
                    System.String.Format("Bias {{0}} is not unity at 0x{{1:X4}}", gainIndex + 1, biasAddresses[gainIndex] + k));
    }}

    // Temporary attenuation prevents a positive transient while LUTs change.
    stage = "temporary guard gain";
    ss.ICRegisterWrite(icName, biasAddresses[0], 4, guardWord);

    for (int band = 0; band < tableAddresses.Length; band++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[band] + 4 * wordIndex;
            byte[] expected = new byte[4];
            for (int k = 0; k < 4; k++) expected[k] = profileTables[band][4 * wordIndex + k];
            stage = System.String.Format("write {profile} B{{0}} word {{1}}", band + 1, wordIndex);
            ss.ICRegisterWrite(icName, address, 4, expected);
            byte[] actual = new byte[4];
            ss.ICRegisterRead(icName, address, 4, ref actual);
            for (int k = 0; k < 4; k++)
                if (actual[k] != expected[k])
                    throw new System.Exception(
                        System.String.Format("Readback mismatch at 0x{{0:X4}}", address + k));
        }}
    }}

    // Restore the common bias progressively after every LUT is valid.
    for (int gainIndex = 0; gainIndex < biasAddresses.Length; gainIndex++)
    {{
        stage = System.String.Format("write prescription bias {{0}}", gainIndex + 1);
        ss.ICRegisterWrite(icName, biasAddresses[gainIndex], 4, biasWord);
        byte[] actual = new byte[4];
        ss.ICRegisterRead(icName, biasAddresses[gainIndex], 4, ref actual);
        for (int k = 0; k < 4; k++)
            if (actual[k] != biasWord[k])
                throw new System.Exception(
                    System.String.Format("Bias readback mismatch at 0x{{0:X4}}", biasAddresses[gainIndex] + k));
    }}

    System.Windows.Forms.MessageBox.Show(
        "PASS: {profile} loaded and verified.\\n\\n" +
        "Eight compressor LUTs updated.\\n" +
        "Three bias stages: {bias_stage_db:.6f} dB each.\\n\\n" +
        "The global CEC1 -20 dB output headroom is NOT included in this initial validation.");
}}
catch (System.OperationCanceledException ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ABORT during: " + stage + "\\n\\n" + ex.Message +
        "\\n\\nRun Link Compile Download; no prescription test should follow this abort.");
}}
catch (System.Exception ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ERROR during: " + stage + "\\n\\n" + ex.ToString() +
        "\\n\\nRun {profile}_restore_unity.sss or Link Compile Download before continuing.");
}}
'''


def render_restore(
    profile: str,
    table_addresses: list[int],
    bias_addresses: list[int],
    table_data: list[bytes],
    bias_word: bytes,
    guard_word: bytes,
) -> str:
    tables = ",\n    ".join(csharp_bytes(data) for data in table_data)
    return f'''// #LANGUAGE# C#
// Safe restoration from {profile}, unity, or a known partially applied state.

string icName = "IC 1";
string stage = "initialization";
int tableWords = 34;
int[] tableAddresses = {csharp_ints(table_addresses)};
int[] biasAddresses = {csharp_ints(bias_addresses)};
byte[] unityWord = {csharp_bytes(UNITY_WORD)};
byte[] guardWord = {csharp_bytes(guard_word)};
byte[] biasWord = {csharp_bytes(bias_word)};
byte[][] profileTables = new byte[][] {{
    {tables}
}};

try
{{
    // Safe order: attenuate the active sum, clear remaining biases, restore LUTs.
    stage = "temporary guard gain";
    ss.ICRegisterWrite(icName, biasAddresses[0], 4, guardWord);
    for (int gainIndex = 1; gainIndex < biasAddresses.Length; gainIndex++)
    {{
        stage = System.String.Format("clear bias {{0}}", gainIndex + 1);
        ss.ICRegisterWrite(icName, biasAddresses[gainIndex], 4, unityWord);
    }}

    for (int band = 0; band < tableAddresses.Length; band++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[band] + 4 * wordIndex;
            byte[] actual = new byte[4];
            stage = System.String.Format("inspect B{{0}} word {{1}}", band + 1, wordIndex);
            ss.ICRegisterRead(icName, address, 4, ref actual);
            bool isUnity = true;
            bool isProfile = true;
            for (int k = 0; k < 4; k++)
            {{
                if (actual[k] != unityWord[k]) isUnity = false;
                if (actual[k] != profileTables[band][4 * wordIndex + k]) isProfile = false;
            }}
            if (!isUnity && !isProfile)
                throw new System.OperationCanceledException(
                    System.String.Format("Unknown LUT value at B{{0}}, 0x{{1:X4}}", band + 1, address));

            stage = System.String.Format("restore B{{0}} word {{1}}", band + 1, wordIndex);
            ss.ICRegisterWrite(icName, address, 4, unityWord);
            byte[] verify = new byte[4];
            ss.ICRegisterRead(icName, address, 4, ref verify);
            for (int k = 0; k < 4; k++)
                if (verify[k] != unityWord[k])
                    throw new System.Exception(
                        System.String.Format("Unity readback mismatch at 0x{{0:X4}}", address + k));
        }}
    }}

    stage = "remove temporary guard";
    ss.ICRegisterWrite(icName, biasAddresses[0], 4, unityWord);
    for (int gainIndex = 0; gainIndex < biasAddresses.Length; gainIndex++)
    {{
        byte[] actual = new byte[4];
        ss.ICRegisterRead(icName, biasAddresses[gainIndex], 4, ref actual);
        for (int k = 0; k < 4; k++)
            if (actual[k] != unityWord[k])
                throw new System.Exception(
                    System.String.Format("Bias did not return to unity at 0x{{0:X4}}", biasAddresses[gainIndex] + k));
    }}

    System.Windows.Forms.MessageBox.Show(
        "PASS: {profile} removed. All eight LUTs and three biases are back at unity.");
}}
catch (System.OperationCanceledException ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ABORT during: " + stage + "\\n\\n" + ex.Message +
        "\\n\\nRun Link Compile Download to guarantee a complete restoration.");
}}
catch (System.Exception ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ERROR during: " + stage + "\\n\\n" + ex.ToString() +
        "\\n\\nRun Link Compile Download before continuing.");
}}
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    prescription_path = resolve_from(config_path, config["prescription_json"])
    export_xml = resolve_from(config_path, config["sigma_export_xml"])
    detector_calibration = None
    detector_calibration_path = None
    if "detector_calibration_file" in config:
        detector_calibration_path = resolve_from(
            config_path, config["detector_calibration_file"]
        )
        detector_calibration = load_json(detector_calibration_path)
    output_dir = resolve_from(config_path, config["output_directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    prescription = load_json(prescription_path)
    if prescription["profile"] != config["profile"]:
        raise ValueError("Config and prescription profile do not match")
    ear_key = f"gain_db_{config['ear']}_band_by_level"
    levels = [float(x) for x in prescription["dynamics"]["input_levels_db_spl"]]
    gains = [[float(x) for x in row] for row in prescription["dynamics"][ear_key]][:8]

    table_config = config["detector_table"]
    detector_points = list(
        range(
            int(table_config["minimum_dbfs"]),
            int(table_config["maximum_dbfs"]) + 1,
            int(table_config["step_db"]),
        )
    )
    if table_config["duplicate_minimum_for_underflow"]:
        detector_points.insert(0, detector_points[0])
    if len(detector_points) != 34:
        raise ValueError(f"ADAU1787 standard-resolution LUT requires 34 words, got {len(detector_points)}")
    spl_points = [x + float(config["cec1_equivalent_0_dbfs_db_spl"]) for x in detector_points]
    desired = [
        [interpolate(spl, levels, band_gains) for spl in spl_points]
        for band_gains in gains
    ]
    b1_calibration_result = None
    legacy_b1_calibration = (
        detector_calibration.get("legacy_b1_low_level_detector_calibration")
        if detector_calibration else None
    )
    if legacy_b1_calibration:
        desired[0], b1_calibration_result = calibrate_b1_three_checkpoints(
            detector_points,
            desired[0],
            legacy_b1_calibration,
            levels,
            gains[0],
        )
    maximum_desired = max(max(row) for row in desired)
    bias_total_db = max(0.0, maximum_desired - float(config["maximum_lut_gain_db"]))
    bias_stage_db = bias_total_db / len(config["bias_cells"])
    residual = [[value - bias_total_db for value in row] for row in desired]

    table_data: list[bytes] = []
    table_manifest: list[dict[str, Any]] = []
    for band_index, row in enumerate(residual, start=1):
        encoded = [fixed_5_23_from_db(value) for value in row]
        table_data.append(b"".join(item[2] for item in encoded))
        table_manifest.append(
            {
                "band": band_index,
                "desired_gain_db": desired[band_index - 1],
                "lut_gain_after_bias_subtraction_db": row,
                "lut_words_hex": [f"0x{item[1]:08X}" for item in encoded],
            }
        )

    _, bias_integer, bias_word = fixed_5_23_from_db(bias_stage_db)
    _, guard_integer, guard_word = fixed_5_23_from_db(float(config["temporary_guard_gain_db"]))
    parameters = export_parameters(export_xml)
    table_addresses = [find_lut_address(parameters, cell) for cell in config["compressor_cells"]]
    bias_addresses = [find_gain_address(parameters, cell) for cell in config["bias_cells"]]

    profile = config["profile"]
    apply_name = f"{profile}_apply_prescription.sss"
    restore_name = f"{profile}_restore_unity.sss"
    (output_dir / apply_name).write_text(
        render_apply(
            profile, table_addresses, bias_addresses, table_data,
            bias_word, guard_word, bias_stage_db,
        ),
        encoding="utf-8",
    )
    (output_dir / restore_name).write_text(
        render_restore(
            profile, table_addresses, bias_addresses, table_data,
            bias_word, guard_word,
        ),
        encoding="utf-8",
    )

    validation_levels = [45.0, 55.0, 65.0, 75.0, 85.0, 95.0]
    with (output_dir / f"{profile}_validation_targets.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        fields = [
            "profile", "band", "centre_hz", "input_level_db_spl",
            "nominal_detector_dbfs", "nominal_electrical_input_dbv",
            "expected_camfit_gain_db", "electrical_mapping_status",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for band_index in range(8):
            for level in validation_levels:
                writer.writerow(
                    {
                        "profile": profile,
                        "band": band_index + 1,
                        "centre_hz": prescription["filterbank"]["centres_hz"][band_index],
                        "input_level_db_spl": f"{level:.1f}",
                        "nominal_detector_dbfs": f"{level - float(config['cec1_equivalent_0_dbfs_db_spl']):.2f}",
                        "nominal_electrical_input_dbv": f"{level - float(config['cec1_equivalent_0_dbfs_db_spl']) - float(config['b1_detector_minus_electrical_input_db']):.2f}",
                        "expected_camfit_gain_db": f"{interpolate(level, levels, gains[band_index]):.6f}",
                        "electrical_mapping_status": "measured B1/50 Hz" if band_index == 0 else "nominal; per-band calibration pending",
                    }
                )

    manifest = {
        "profile": profile,
        "ear": config["ear"],
        "source": {
            "config": str(config_path.relative_to(WORKSPACE)),
            "config_sha256": sha256(config_path),
            "prescription": str(prescription_path.relative_to(WORKSPACE)),
            "prescription_sha256": sha256(prescription_path),
            "sigma_export_xml": str(export_xml.relative_to(WORKSPACE)),
            "sigma_export_xml_sha256": sha256(export_xml),
            "detector_calibration": (
                str(detector_calibration_path.relative_to(WORKSPACE))
                if detector_calibration_path else None
            ),
            "detector_calibration_sha256": (
                sha256(detector_calibration_path)
                if detector_calibration_path else None
            ),
        },
        "mapping": {
            "detector_points_dbfs": detector_points,
            "input_levels_db_spl": spl_points,
            "equivalent_0_dbfs_db_spl": config["cec1_equivalent_0_dbfs_db_spl"],
            "maximum_desired_gain_db": maximum_desired,
            "common_bias_total_db": bias_total_db,
            "bias_per_stage_db": bias_stage_db,
            "bias_word_hex": f"0x{bias_integer:08X}",
            "temporary_guard_db": config["temporary_guard_gain_db"],
            "temporary_guard_word_hex": f"0x{guard_integer:08X}",
            "global_output_headroom_db": config["global_output_headroom_db"],
            "global_output_headroom_status": config["global_output_headroom_status"],
        },
        "addresses": {
            "compressor_lut_external_byte_addresses": [f"0x{x:04X}" for x in table_addresses],
            "bias_external_byte_addresses": [f"0x{x:04X}" for x in bias_addresses],
        },
        "calibration_scope": config["calibration_scope"],
        "b1_low_level_detector_calibration": b1_calibration_result,
        "tables": table_manifest,
    }
    (output_dir / f"{profile}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checksums = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            checksums.append(f"{sha256(path)}  {path.name}")
    (output_dir / "SHA256SUMS.txt").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8"
    )
    print(f"Generated {profile} SigmaStudio scripts in {output_dir}")
    print(f"Maximum CAMFIT gain in LUT range: {maximum_desired:.6f} dB")
    print(f"Common bias: {bias_total_db:.6f} dB ({bias_stage_db:.6f} dB per stage)")


if __name__ == "__main__":
    main()
