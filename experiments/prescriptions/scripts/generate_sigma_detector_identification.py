#!/usr/bin/env python3
"""Generate SigmaStudio detector-identification scripts and model constants."""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = (
    WORKSPACE / "tiresias-eval-sigma" / "config" / "detector_calibration_eval.json"
)
UNITY_WORD = bytes.fromhex("00800000")
TABLE_WORDS = 34


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_from(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_modules(export_xml: Path) -> list[dict[str, Any]]:
    root = ET.parse(export_xml).getroot()
    result: list[dict[str, Any]] = []
    for module in root.findall(".//Module"):
        cell = module.findtext("CellName")
        if not cell:
            continue
        result.append(
            {
                "cell": cell,
                "description": module.findtext(".//Description", ""),
                "parameters": [
                    {
                        "name": item.findtext("Name", ""),
                        "address": int(item.findtext("Address", "-1")),
                        "size": int(item.findtext("Size", "0")),
                        "value": float(item.findtext("Value", "0")),
                    }
                    for item in module.findall(".//ModuleParameter")
                ],
            }
        )
    return result


def find_lut_address(modules: list[dict[str, Any]], cell: str) -> int:
    module = next(item for item in modules if item["cell"] == cell)
    candidates = [
        item for item in module["parameters"]
        if item["size"] == 136 and item["name"].lower().endswith("tab")
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected one 136-byte LUT for {cell}, found {candidates}")
    return int(candidates[0]["address"])


def find_gain_address(modules: list[dict[str, Any]], cell: str) -> int:
    module = next(item for item in modules if item["cell"] == cell)
    candidates = [item for item in module["parameters"] if item["size"] == 4]
    if len(candidates) != 1:
        raise ValueError(f"Expected one four-byte gain for {cell}, found {candidates}")
    return int(candidates[0]["address"])


def fixed_5_23_from_db(gain_db: float) -> bytes:
    value = int(round((10.0 ** (gain_db / 20.0)) * (1 << 23)))
    if not 0 <= value < 0x08000000:
        raise ValueError(f"Gain {gain_db:.6f} dB is outside positive 5.23 range")
    return value.to_bytes(4, byteorder="big", signed=False)


def detector_points() -> list[float]:
    unique = [float(value) for value in range(-90, 7, 3)]
    return [unique[0], *unique]


def identification_gain_db(detector_dbfs: float) -> float:
    return -0.25 * detector_dbfs - 10.0


def csharp_bytes(data: bytes) -> str:
    return "new byte[] { " + ", ".join(f"0x{x:02X}" for x in data) + " }"


def csharp_ints(values: list[int]) -> str:
    return "new int[] { " + ", ".join(f"0x{x:04X}" for x in values) + " }"


def render_apply(
    band: int,
    table_addresses: list[int],
    bias_addresses: list[int],
    calibration_words: list[bytes],
) -> str:
    words = ",\n    ".join(csharp_bytes(word) for word in calibration_words)
    return f'''// #LANGUAGE# C#
// Detector identification for B{band}. Run only after Link Compile Download.
// LUT equation: gain_dB = -0.25 * detector_dBFS - 10.

string icName = "IC 1";
string stage = "initialization";
int targetBand = {band - 1};
int tableWords = {TABLE_WORDS};
int[] tableAddresses = {csharp_ints(table_addresses)};
int[] biasAddresses = {csharp_ints(bias_addresses)};
byte[] unityWord = {csharp_bytes(UNITY_WORD)};
byte[][] calibrationWords = new byte[][] {{
    {words}
}};

try
{{
    for (int bandIndex = 0; bandIndex < tableAddresses.Length; bandIndex++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[bandIndex] + 4 * wordIndex;
            byte[] actual = new byte[4];
            stage = System.String.Format("pre-flight B{{0}} word {{1}}", bandIndex + 1, wordIndex);
            ss.ICRegisterRead(icName, address, 4, ref actual);
            for (int k = 0; k < 4; k++)
                if (actual[k] != unityWord[k])
                    throw new System.OperationCanceledException(
                        System.String.Format("B{{0}} is not unity at 0x{{1:X4}}", bandIndex + 1, address + k));
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

    for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
    {{
        int address = tableAddresses[targetBand] + 4 * wordIndex;
        stage = System.String.Format("write B{band} word {{0}}", wordIndex);
        ss.ICRegisterWrite(icName, address, 4, calibrationWords[wordIndex]);
        byte[] actual = new byte[4];
        ss.ICRegisterRead(icName, address, 4, ref actual);
        for (int k = 0; k < 4; k++)
            if (actual[k] != calibrationWords[wordIndex][k])
                throw new System.Exception(
                    System.String.Format("Readback mismatch at 0x{{0:X4}}", address + k));
    }}

    System.Windows.Forms.MessageBox.Show(
        "PASS: detector-identification LUT loaded in B{band}.\\n\\n" +
        "Keep B1-B8 biases at unity. Measure the stationary spectral component, " +
        "then run detector_identification_restore_all_unity.sss or Link Compile Download.");
}}
catch (System.OperationCanceledException ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ABORT during: " + stage + "\\n\\n" + ex.Message +
        "\\n\\nRun Link Compile Download before repeating. No parameter was intentionally changed after the failed pre-flight.");
}}
catch (System.Exception ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ERROR during: " + stage + "\\n\\n" + ex.ToString() +
        "\\n\\nRun detector_identification_restore_all_unity.sss or Link Compile Download.");
}}
'''


def render_restore(
    table_addresses: list[int],
    bias_addresses: list[int],
    calibration_words: list[bytes],
) -> str:
    words = ",\n    ".join(csharp_bytes(word) for word in calibration_words)
    return f'''// #LANGUAGE# C#
// Restore all compressor LUTs after a detector-identification measurement.

string icName = "IC 1";
string stage = "initialization";
int tableWords = {TABLE_WORDS};
int[] tableAddresses = {csharp_ints(table_addresses)};
int[] biasAddresses = {csharp_ints(bias_addresses)};
byte[] unityWord = {csharp_bytes(UNITY_WORD)};
byte[][] calibrationWords = new byte[][] {{
    {words}
}};

try
{{
    for (int gainIndex = 0; gainIndex < biasAddresses.Length; gainIndex++)
    {{
        byte[] actual = new byte[4];
        ss.ICRegisterRead(icName, biasAddresses[gainIndex], 4, ref actual);
        for (int k = 0; k < 4; k++)
            if (actual[k] != unityWord[k])
                throw new System.OperationCanceledException(
                    System.String.Format("Bias {{0}} is not unity at 0x{{1:X4}}", gainIndex + 1, biasAddresses[gainIndex] + k));
    }}

    for (int bandIndex = 0; bandIndex < tableAddresses.Length; bandIndex++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[bandIndex] + 4 * wordIndex;
            byte[] actual = new byte[4];
            stage = System.String.Format("inspect B{{0}} word {{1}}", bandIndex + 1, wordIndex);
            ss.ICRegisterRead(icName, address, 4, ref actual);
            bool isUnity = true;
            bool isCalibration = true;
            for (int k = 0; k < 4; k++)
            {{
                if (actual[k] != unityWord[k]) isUnity = false;
                if (actual[k] != calibrationWords[wordIndex][k]) isCalibration = false;
            }}
            if (!isUnity && !isCalibration)
                throw new System.OperationCanceledException(
                    System.String.Format("Unknown LUT value at B{{0}}, 0x{{1:X4}}", bandIndex + 1, address));
        }}
    }}

    for (int bandIndex = 0; bandIndex < tableAddresses.Length; bandIndex++)
    {{
        for (int wordIndex = 0; wordIndex < tableWords; wordIndex++)
        {{
            int address = tableAddresses[bandIndex] + 4 * wordIndex;
            stage = System.String.Format("restore B{{0}} word {{1}}", bandIndex + 1, wordIndex);
            ss.ICRegisterWrite(icName, address, 4, unityWord);
            byte[] actual = new byte[4];
            ss.ICRegisterRead(icName, address, 4, ref actual);
            for (int k = 0; k < 4; k++)
                if (actual[k] != unityWord[k])
                    throw new System.Exception(
                        System.String.Format("Unity readback mismatch at 0x{{0:X4}}", address + k));
        }}
    }}

    System.Windows.Forms.MessageBox.Show(
        "PASS: all eight compressor LUTs are back at unity.");
}}
catch (System.OperationCanceledException ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ABORT during: " + stage + "\\n\\n" + ex.Message +
        "\\n\\nRun Link Compile Download to guarantee restoration.");
}}
catch (System.Exception ex)
{{
    System.Windows.Forms.MessageBox.Show(
        "ERROR during: " + stage + "\\n\\n" + ex.ToString() +
        "\\n\\nRun Link Compile Download before continuing.");
}}
'''


def module_parameters(module: dict[str, Any]) -> dict[str, float]:
    return {item["name"]: float(item["value"]) for item in module["parameters"]}


def biquad(
    parameters: dict[str, float], prefix: str, index: int, z: complex
) -> complex:
    b0 = parameters[f"{prefix}B0_{index}"]
    b1 = parameters[f"{prefix}B1_{index}"]
    b2 = parameters[f"{prefix}B2_{index}"]
    a1 = parameters[f"{prefix}A1_{index}"]
    a2 = parameters[f"{prefix}A2_{index}"]
    return (b0 + b1 / z + b2 / z**2) / (1.0 - a1 / z - a2 / z**2)


def filterbank_contributions(
    modules: list[dict[str, Any]], frequency_hz: float, sample_rate_hz: float
) -> tuple[list[complex], complex]:
    z = cmath.exp(1j * 2.0 * math.pi * frequency_hz / sample_rate_hz)
    crossover_modules = []
    for module in modules:
        if not module["cell"].startswith("filterbank.Crossover-"):
            continue
        match = re.search(r"FrequencyLow\[ ([0-9.]+) \]", module["description"])
        if not match:
            raise ValueError(f"Cannot find crossover frequency for {module['cell']}")
        parameters = module_parameters(module)
        prefix = next(name.split("LowInvert")[0] for name in parameters if "LowInvert" in name)
        crossover_modules.append((float(match.group(1)), parameters, prefix))
    crossover_modules.sort(key=lambda item: item[0])

    lows: list[complex] = []
    highs: list[complex] = []
    for _, parameters, prefix in crossover_modules:
        lows.append(
            biquad(parameters, prefix, 0, z) * biquad(parameters, prefix, 1, z)
        )
        highs.append(
            biquad(parameters, prefix, 2, z) * biquad(parameters, prefix, 3, z)
        )

    raw_bands: list[complex] = []
    remainder = 1.0 + 0.0j
    for low, high in zip(lows, highs):
        raw_bands.append(remainder * low)
        remainder *= high
    raw_bands.append(remainder)

    allpass_modules = []
    for module in modules:
        if not module["cell"].startswith("phasecomp.AllPass-"):
            continue
        match = re.search(r"Frequency1\[ ([0-9.]+) \]", module["description"])
        if not match:
            raise ValueError(f"Cannot find all-pass frequency for {module['cell']}")
        parameters = module_parameters(module)
        prefix = next(name[:-3] for name in parameters if name.endswith("0B1"))
        b0 = parameters[f"{prefix}0B1"]
        b1 = parameters[f"{prefix}1B1"]
        b2 = parameters[f"{prefix}2B1"]
        a1 = parameters[f"{prefix}1A1"]
        a2 = parameters[f"{prefix}2A1"]
        response = (b0 + b1 / z + b2 / z**2) / (1.0 - a1 / z - a2 / z**2)
        allpass_modules.append((float(match.group(1)), response))
    allpass_modules.sort(key=lambda item: item[0])
    allpasses = [item[1] for item in allpass_modules]

    contributions: list[complex] = []
    for target in range(9):
        gains = [0.0] * 9
        gains[target] = 1.0
        output = raw_bands[0] * gains[0] * allpasses[0] + raw_bands[1] * gains[1]
        for band_index in range(2, 8):
            output = output * allpasses[band_index - 1] + raw_bands[band_index] * gains[band_index]
        output += raw_bands[8] * gains[8]
        contributions.append(output)
    return contributions, sum(contributions)


def model_constants(
    modules: list[dict[str, Any]], band: int, frequency_hz: float, sample_rate_hz: float
) -> dict[str, float]:
    contributions, unity = filterbank_contributions(modules, frequency_hz, sample_rate_hz)
    target = contributions[band - 1]
    remainder = unity - target
    return {
        "target_real": target.real,
        "target_imag": target.imag,
        "remainder_real": remainder.real,
        "remainder_imag": remainder.imag,
        "target_magnitude": abs(target),
        "remainder_magnitude": abs(remainder),
        "unity_magnitude": abs(unity),
        "target_squared": abs(target) ** 2,
        "cross_term": 2.0 * (target.real * remainder.real + target.imag * remainder.imag),
        "remainder_squared": abs(remainder) ** 2,
        "unity_squared": abs(unity) ** 2,
        "phase_difference_degrees": math.degrees(cmath.phase(target / remainder)),
    }


def unity_model_maximum_error_db(
    modules: list[dict[str, Any]], sample_rate_hz: float
) -> float:
    maximum = 0.0
    for index in range(2000):
        fraction = index / 1999.0
        frequency_hz = 20.0 * ((20000.0 / 20.0) ** fraction)
        _, unity = filterbank_contributions(modules, frequency_hz, sample_rate_hz)
        error_db = abs(20.0 * math.log10(abs(unity)))
        maximum = max(maximum, error_db)
    return maximum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    export_xml = resolve_from(config_path, config["sigma_export_xml"])
    output_dir = resolve_from(config_path, config["output_directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    modules = export_modules(export_xml)
    table_addresses = [
        find_lut_address(modules, cell) for cell in config["compressor_cells"]
    ]
    bias_addresses = [
        find_gain_address(modules, cell) for cell in config["bias_cells"]
    ]
    points = detector_points()
    calibration_words = [
        fixed_5_23_from_db(identification_gain_db(point)) for point in points
    ]

    for band in range(1, 9):
        (output_dir / f"B{band}_detector_identification.sss").write_text(
            render_apply(band, table_addresses, bias_addresses, calibration_words),
            encoding="utf-8",
        )
    (output_dir / "detector_identification_restore_all_unity.sss").write_text(
        render_restore(table_addresses, bias_addresses, calibration_words),
        encoding="utf-8",
    )

    sample_rate_hz = float(config["sample_rate_hz"])
    levels = [float(value) for value in config["validation_levels_db_spl"]]
    frequencies = [float(value) for value in config["band_test_frequencies_hz"]]
    if len(frequencies) != 8:
        raise ValueError("The shared detector campaign requires eight test frequencies")
    manifest = {
        "purpose": "shared stationary spectral detector identification for N1-N10",
        "source": {
            "config": str(config_path.relative_to(WORKSPACE)),
            "config_sha256": sha256(config_path),
            "sigma_export_xml": str(export_xml.relative_to(WORKSPACE)),
            "sigma_export_xml_sha256": sha256(export_xml),
        },
        "identification_lut": {
            "equation_gain_db": "-0.25 * detector_dbfs - 10",
            "inverse_detector_dbfs": "-4 * (gain_db + 10)",
            "detector_points_dbfs": points,
            "gain_points_db": [identification_gain_db(point) for point in points],
        },
        "sample_rate_hz": sample_rate_hz,
        "unity_model_maximum_error_db": unity_model_maximum_error_db(
            modules, sample_rate_hz
        ),
        "measurements": [],
    }
    for band, frequency_hz in enumerate(frequencies, start=1):
        manifest["measurements"].append(
            {
                "band": band,
                "frequency_hz": frequency_hz,
                "equivalent_levels_db_spl": levels,
                "rew_dac_levels_dbv": [
                    round(
                        level + float(config["rew_dac_offset_from_equivalent_spl_db"]),
                        2,
                    )
                    for level in levels
                ],
                "model": model_constants(
                    modules, band, frequency_hz, sample_rate_hz
                ),
            }
        )
    (output_dir / "detector_identification_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readme = "# Calibração comum dos detectores B1–B8\n\n"
    readme += "Esta calibração pertence ao EVAL, ao banco de filtros e aos blocos RMS — não a uma prescrição. Execute-a uma vez e reutilize o resultado em N1–N10.\n\n"
    readme += "## Condição da interface\n\n"
    readme += "A entrada da Focusrite Scarlett 18i8 deve permanecer ajustada e calibrada para **1 Vrms = 0 dBFS (full scale)**, com o REW exibindo dBV. Mudar o ganho da Scarlett invalida esta calibração.\n\n"
    readme += "## Procedimento por banda\n\n"
    readme += "1. Execute **Link Compile Download**. Todas as LUTs e os três biases devem estar em unity.\n"
    readme += "2. Gere o seno estacionário na frequência indicada na planilha e meça a componente espectral unity nos quatro níveis.\n"
    readme += "3. Rode `B<n>_detector_identification.sss` uma única vez.\n"
    readme += "4. Repita os quatro níveis, aguardando pelo menos 2 s após cada mudança.\n"
    readme += "5. Rode `detector_identification_restore_all_unity.sss` antes da próxima banda.\n\n"
    readme += "Preencha somente as colunas amarelas da planilha `rew/detector-calibration/ADAU1787_EVAL_detector_calibration.xlsx`. Não use sweep.\n"
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    checksums = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            checksums.append(f"{sha256(path)}  {path.name}")
    (output_dir / "SHA256SUMS.txt").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8"
    )
    print(f"Generated detector-identification scripts in {output_dir}")


if __name__ == "__main__":
    main()
