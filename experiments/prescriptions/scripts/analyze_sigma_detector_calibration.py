#!/usr/bin/env python3
"""Analyze the shared ADAU1787 EVAL detector-calibration workbook.

The workbook may be exported from Apple Numbers.  This script intentionally
uses only the Python standard library to read the small XLSX table so the
calibration can be reproduced without Excel, Numbers, pandas, or openpyxl.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[3]
DEFAULT_WORKBOOK = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "rew"
    / "detector-calibration"
    / "ADAU1787_EVAL_detector_calibration.xlsx"
)
DEFAULT_CONFIG = (
    WORKSPACE / "tiresias-eval-sigma" / "config" / "detector_calibration_eval.json"
)
DEFAULT_MANIFEST = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "scripts"
    / "generated"
    / "detector-identification"
    / "detector_identification_manifest.json"
)
DEFAULT_OUTPUT_DIR = (
    WORKSPACE / "tiresias-eval-sigma" / "rew" / "detector-calibration" / "results"
)

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    value = 0
    for character in letters:
        value = value * 26 + ord(character.upper()) - ord("A") + 1
    return value - 1


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    result = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        result.append("".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")))
    return result


def sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        if sheet.attrib["name"] == sheet_name:
            relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
            target = targets[relationship_id].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError(f"Worksheet {sheet_name!r} was not found")


def cell_value(cell: ET.Element, strings: list[str]) -> Any:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return None
    raw = value_node.text
    if kind == "s":
        return strings[int(raw)]
    if kind in {"str", "e"}:
        return raw
    if kind == "b":
        return raw == "1"
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def read_sheet(path: Path, sheet_name: str) -> list[list[Any]]:
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        root = ET.fromstring(archive.read(sheet_path(archive, sheet_name)))
        rows: list[list[Any]] = []
        for row in root.findall(f".//{{{MAIN_NS}}}row"):
            values: dict[int, Any] = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                values[column_index(cell.attrib["r"])] = cell_value(cell, strings)
            if values:
                width = max(values) + 1
                rows.append([values.get(index) for index in range(width)])
            else:
                rows.append([])
        return rows


def table_records(rows: list[list[Any]], header_name: str) -> list[dict[str, Any]]:
    header_index = next(
        index for index, row in enumerate(rows) if row and row[0] == header_name
    )
    headers = [str(value) for value in rows[header_index]]
    records = []
    for row in rows[header_index + 1 :]:
        if not row or row[0] in {None, ""}:
            continue
        padded = row + [None] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded)))
    return records


def infer_detector(record: dict[str, Any], model: dict[str, float]) -> dict[str, float]:
    unity = float(record["unity_component_dbv"])
    identification = float(record["identification_component_dbv"])
    insertion = identification - unity
    ratio = 10.0 ** (insertion / 20.0)
    a = float(model["target_squared"])
    b = float(model["cross_term"])
    c = float(model["remainder_squared"]) - ratio**2 * float(model["unity_squared"])
    discriminant = b**2 - 4.0 * a * c
    if discriminant < -1e-12:
        raise ValueError(f"Negative discriminant for {record['test_id']}: {discriminant}")
    discriminant = max(discriminant, 0.0)
    roots = [
        (-b + math.sqrt(discriminant)) / (2.0 * a),
        (-b - math.sqrt(discriminant)) / (2.0 * a),
    ]
    positive_roots = [value for value in roots if value > 0.0]
    if not positive_roots:
        raise ValueError(f"No positive compressor gain for {record['test_id']}")
    compressor_linear_gain = max(positive_roots)
    identification_gain_db = 20.0 * math.log10(compressor_linear_gain)
    detector_dbfs = -4.0 * (identification_gain_db + 10.0)
    return {
        "insertion_db": insertion,
        "output_ratio": ratio,
        "discriminant": discriminant,
        "compressor_linear_gain": compressor_linear_gain,
        "identification_gain_db": identification_gain_db,
        "detector_dbfs": detector_dbfs,
    }


def linear_fit(x: list[float], y: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(x)
    mean_y = statistics.fmean(y)
    denominator = sum((value - mean_x) ** 2 for value in x)
    slope = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / denominator
    intercept = mean_y - slope * mean_x
    residuals = [b - (slope * a + intercept) for a, b in zip(x, y)]
    rms = math.sqrt(statistics.fmean(value**2 for value in residuals))
    return slope, intercept, rms


def round_list(values: list[float], digits: int = 6) -> list[float]:
    return [round(value, digits) for value in values]


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def markdown_summary(
    band_results: dict[str, dict[str, Any]],
    all_rows: list[dict[str, Any]],
    cached_difference: float,
) -> str:
    unity_errors = [row["unity_tracking_error_db"] for row in all_rows]
    lines = [
        "# Resultado da calibração comum dos detectores B1–B8",
        "",
        "## Condição de medição",
        "",
        "A entrada da Focusrite Scarlett 18i8 foi ajustada e calibrada para **1 Vrms = 0 dBFS (full scale)**. O REW foi configurado para exibir a entrada diretamente em dBV sob essa condição.",
        "",
        "O ensaio usou seno estacionário, leitura da componente espectral na frequência de cada banda e o ADAU1787 EVAL com a topologia SigmaStudio atual.",
        "",
        "## Integridade",
        "",
        f"- Registros completos: {len(all_rows)}/32.",
        f"- Erro máximo entre esta análise independente e os resultados armazenados na aba Analysis: {cached_difference:.9f} dB.",
        f"- Rastreamento unity médio (saída menos DAC do REW): {statistics.fmean(unity_errors):.3f} dB.",
        f"- Faixa do rastreamento unity: {min(unity_errors):.3f} a {max(unity_errors):.3f} dB.",
        "",
        "## Mapa medido",
        "",
        "| Banda | f (Hz) | detector @45 | @65 | @85 | @95 dB SPL | Diagnóstico |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, result in band_results.items():
        detector = result["detector_dbfs"]
        lines.append(
            f"| {key} | {result['frequency_hz']:.0f} | {detector[0]:.2f} | {detector[1]:.2f} | {detector[2]:.2f} | {detector[3]:.2f} | {result['diagnostic']} |"
        )
    lines += [
        "",
        "## Interpretação",
        "",
        "B2–B8 acompanham o nível aplicado de forma aproximadamente 1:1. A diferença entre detector e nível elétrico é pequena e específica por banda; por isso o mapa medido substitui a hipótese nominal única.",
        "",
        "B1 não acompanha os dois níveis mais baixos: o detector fica próximo de −40 dBFS a 45 dB SPL equivalente e só converge para uma inclinação aproximadamente unitária nos níveis altos. Isso é compatível com um piso de energia de baixa frequência dentro da banda — por exemplo ruído, hum ou conteúdo residual — porque o detector RMS integra toda B1, embora a leitura do REW observe apenas a componente de 177 Hz.",
        "",
        "Consequência: abaixo do primeiro ponto confiável, B1 não consegue distinguir níveis de entrada diferentes. A geração das prescrições deve manter o ganho de 45 dB SPL nessa região, e não extrapolar uma reta fictícia. B2–B8 podem usar interpolação por trechos e extrapolação pelas extremidades.",
        "",
        "## Próxima validação recomendada",
        "",
        "Antes de tratar o comportamento de B1 como propriedade definitiva do ADAU1787, medir o espectro interno/saída de B1 sem seno e verificar especialmente 50/60 Hz e seus harmônicos. A prescrição pode ser gerada e validada desde já com a política conservadora descrita acima.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    workbook_path = args.workbook.resolve()
    config_path = args.config.resolve()
    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    measurements = table_records(read_sheet(workbook_path, "Measurements"), "test_id")
    if len(measurements) != 32:
        raise ValueError(f"Expected 32 measurements, found {len(measurements)}")
    required = {"unity_component_dbv", "identification_component_dbv"}
    for record in measurements:
        missing = [name for name in required if record.get(name) in {None, ""}]
        if missing:
            raise ValueError(f"Missing {missing} in {record['test_id']}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    models = {
        int(item["band"]): item["model"] for item in manifest["measurements"]
    }
    analysis_cached = table_records(read_sheet(workbook_path, "Analysis"), "test_id")
    cached_detector = {
        str(record["test_id"]): float(record["detector_dbfs"])
        for record in analysis_cached
        if record.get("detector_dbfs") not in {None, ""}
    }
    if len(cached_detector) != 32:
        raise ValueError(
            "The exported workbook does not contain all 32 cached Analysis results"
        )

    analysis_rows: list[dict[str, Any]] = []
    for record in measurements:
        band = int(record["band"])
        inferred = infer_detector(record, models[band])
        row = {
            "test_id": str(record["test_id"]),
            "band": band,
            "frequency_hz": float(record["frequency_hz"]),
            "equivalent_level_db_spl": float(record["equivalent_level_db_spl"]),
            "rew_dac_output_dbv": float(record["rew_dac_output_dbv"]),
            "unity_component_dbv": float(record["unity_component_dbv"]),
            "identification_component_dbv": float(record["identification_component_dbv"]),
            **inferred,
        }
        row["unity_tracking_error_db"] = (
            row["unity_component_dbv"] - row["rew_dac_output_dbv"]
        )
        row["detector_minus_electrical_input_db"] = (
            row["detector_dbfs"] - row["rew_dac_output_dbv"]
        )
        analysis_rows.append(row)

    cached_differences = [
        abs(row["detector_dbfs"] - cached_detector[row["test_id"]])
        for row in analysis_rows
        if row["test_id"] in cached_detector
    ]
    cached_difference = max(cached_differences, default=0.0)

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in analysis_rows:
        grouped[int(row["band"])].append(row)

    band_results: dict[str, dict[str, Any]] = {}
    for band in range(1, 9):
        rows = sorted(grouped[band], key=lambda item: item["equivalent_level_db_spl"])
        levels = [row["equivalent_level_db_spl"] for row in rows]
        detector = [row["detector_dbfs"] for row in rows]
        electrical = [row["rew_dac_output_dbv"] for row in rows]
        slope, intercept, fit_rms = linear_fit(levels, detector)
        high_slope = (detector[-1] - detector[-2]) / (levels[-1] - levels[-2])
        step_ratios = [
            (detector[index + 1] - detector[index])
            / (levels[index + 1] - levels[index])
            for index in range(len(levels) - 1)
        ]
        low_level_floor = min(step_ratios) < 0.8
        diagnostic = (
            "piso/contaminação em nível baixo"
            if low_level_floor
            else "mapeamento aproximadamente linear"
        )
        band_results[f"B{band}"] = {
            "band": band,
            "frequency_hz": rows[0]["frequency_hz"],
            "equivalent_input_level_db_spl": levels,
            "rew_dac_output_dbv": electrical,
            "unity_component_dbv": [row["unity_component_dbv"] for row in rows],
            "identification_component_dbv": [
                row["identification_component_dbv"] for row in rows
            ],
            "insertion_db": round_list([row["insertion_db"] for row in rows]),
            "identification_gain_db": round_list(
                [row["identification_gain_db"] for row in rows]
            ),
            "detector_dbfs": round_list(detector),
            "detector_minus_electrical_input_db": round_list(
                [row["detector_minus_electrical_input_db"] for row in rows]
            ),
            "linear_fit_detector_from_spl": {
                "slope_dbfs_per_db_spl": round(slope, 9),
                "intercept_dbfs": round(intercept, 9),
                "rms_residual_db": round(fit_rms, 9),
            },
            "high_level_slope_dbfs_per_db_spl": round(high_slope, 9),
            "step_slopes_dbfs_per_db_spl": round_list(step_ratios, 9),
            "low_level_floor_detected": low_level_floor,
            "below_lowest_detector_policy": (
                "hold equivalent SPL at 45 dB because lower levels are not distinguishable"
                if low_level_floor
                else "linear extrapolation from the two lowest measured checkpoints"
            ),
            "above_highest_detector_policy": (
                "linear extrapolation from the two highest measured checkpoints"
            ),
            "diagnostic": diagnostic,
        }

    unity_errors = [row["unity_tracking_error_db"] for row in analysis_rows]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(
        {
            "status": "campaign_complete_with_b1_low_level_floor",
            "measurement_source": {
                "workbook": str(workbook_path.relative_to(WORKSPACE)),
                "workbook_sha256": sha256(workbook_path),
                "workbook_origin": "Apple Numbers export to Microsoft Excel 2007+ XLSX",
            },
            "measurement_conditions": {
                "capture_interface": "Focusrite Scarlett 18i8",
                "scarlett_input_full_scale_vrms": 1.0,
                "scarlett_input_gain_condition": (
                    "Input gain set and REW calibrated so that 1 Vrms corresponds to 0 dBFS full scale"
                ),
                "rew_input_display_unit": "dBV",
                "dut": "ADAU1787 EVAL",
                "power_and_routing": "current SigmaStudio EVAL bench configuration",
            },
            "analysis_method": {
                "identification_lut_gain_db": "-0.25 * detector_dbfs - 10",
                "inverse_detector_dbfs": "-4 * (identification_gain_db + 10)",
                "filterbank_recombination_model": (
                    "complex target-band plus complex remainder from the SigmaStudio export"
                ),
                "script": str(Path(__file__).resolve().relative_to(WORKSPACE)),
            },
            "quality_control": {
                "complete_measurements": len(analysis_rows),
                "expected_measurements": 32,
                "maximum_difference_from_workbook_cached_analysis_db": round(
                    cached_difference, 12
                ),
                "unity_tracking_error_db": {
                    "mean": round(statistics.fmean(unity_errors), 9),
                    "minimum": round(min(unity_errors), 9),
                    "maximum": round(max(unity_errors), 9),
                    "population_standard_deviation": round(
                        statistics.pstdev(unity_errors), 9
                    ),
                },
                "flags": [
                    "B1 detector has a low-level floor/nonlinear region near -40 dBFS",
                    "B7 at 65 dB SPL produced exactly 0.00 dB measured insertion; the inversion remains well-defined",
                ],
            },
            "measured_band_calibration": band_results,
        }
    )
    if "legacy_b1_low_level_detector_calibration" in config:
        config["legacy_b1_low_level_detector_calibration"]["status"] = (
            "superseded by the common B1-B8 campaign; retained for historical traceability"
        )
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    csv_rows = []
    for row in analysis_rows:
        csv_rows.append(
            {
                key: (round(value, 9) if isinstance(value, float) else value)
                for key, value in row.items()
            }
        )
    write_csv(output_dir / "detector_calibration_results.csv", csv_rows)
    (output_dir / "detector_calibration_results.json").write_text(
        json.dumps(
            {
                "source_workbook": str(workbook_path.relative_to(WORKSPACE)),
                "source_workbook_sha256": sha256(workbook_path),
                "measurement_conditions": config["measurement_conditions"],
                "quality_control": config["quality_control"],
                "bands": band_results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "DETECTOR_CALIBRATION_RESULT.md").write_text(
        markdown_summary(band_results, analysis_rows, cached_difference),
        encoding="utf-8",
    )

    print(f"Analyzed {len(analysis_rows)} measurements")
    print(f"Maximum workbook cross-check difference: {cached_difference:.12f} dB")
    print(f"Updated {config_path.relative_to(WORKSPACE)}")
    print(f"Wrote results to {output_dir.relative_to(WORKSPACE)}")


if __name__ == "__main__":
    main()
