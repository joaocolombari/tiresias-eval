#!/usr/bin/env python3
"""Process the clean-lab REW campaign and compare Sigma, model, and openMHA."""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np


WORKSPACE = Path(__file__).resolve().parents[3]
CAMPAIGN = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
)
CONFIG_PATH = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "config"
    / "prescription_campaign_2026-08-14.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_rew(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, str]]:
    header = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.startswith("*"):
                break
            header.append(line.rstrip())
    data = np.loadtxt(path, comments="*")
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Unexpected REW export: {path}")
    metadata = {"header": "\n".join(header)}
    for key in ("Format", "Measurement", "Smoothing", "Dated"):
        match = re.search(rf"^\* {key}:\s*(.+)$", metadata["header"], re.MULTILINE)
        metadata[key.lower()] = match.group(1).strip() if match else ""
    return data[:, 0], data[:, 1], metadata


def local_median(
    frequencies: np.ndarray,
    values: np.ndarray,
    query: float,
    total_width_octaves: float,
) -> float:
    mask = np.abs(np.log2(frequencies / query)) <= total_width_octaves / 2.0
    selected = values[mask]
    if selected.size:
        return float(np.median(selected))
    return float(np.interp(query, frequencies, values))


def profile_svg(
    profile: str,
    levels: list[int],
    rows: list[dict[str, object]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 960
    left, right, top, bottom, gap = 90, 30, 55, 65, 55
    panel_height = (height - top - bottom - gap * (len(levels) - 1)) / len(levels)
    plot_width = width - left - right
    gains = [float(row["sigma_measured_gain_db"]) for row in rows]
    gains += [float(row["sigma_expected_gain_db"]) for row in rows]
    mha_values = [
        float(row["openmha_gain_db"])
        for row in rows
        if str(row["openmha_gain_db"]) != ""
    ]
    gains += mha_values
    y_min = math.floor((min(gains) - 2.0) / 5.0) * 5.0
    y_max = math.ceil((max(gains) + 2.0) / 5.0) * 5.0
    if y_max <= y_min:
        y_max = y_min + 5.0

    def xcoord(frequency: float) -> float:
        return left + plot_width * math.log10(frequency / 100.0) / 2.0

    def ycoord(value: float, panel: int) -> float:
        panel_top = top + panel * (panel_height + gap)
        return panel_top + panel_height * (y_max - value) / (y_max - y_min)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#202124}.title{font-size:20px;font-weight:700}.label{font-size:14px}.small{font-size:12px}</style>',
        f'<text x="600" y="28" text-anchor="middle" class="title">{profile} — Sigma medido, modelo e openMHA</text>',
    ]
    for panel, level in enumerate(levels):
        selected = [row for row in rows if int(row["level_db_spl"]) == level]
        panel_top = top + panel * (panel_height + gap)
        for ytick in np.linspace(y_min, y_max, 6):
            y = ycoord(float(ytick), panel)
            lines += [
                f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#e2e2e2"/>',
                f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" class="small">{ytick:.0f}</text>',
            ]
        for xtick in (100, 200, 500, 1000, 2000, 5000, 10000):
            x = xcoord(float(xtick))
            lines.append(f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" y2="{panel_top+panel_height:.2f}" stroke="#eeeeee"/>')
            if panel == len(levels) - 1:
                label = f"{xtick//1000}k" if xtick >= 1000 else str(xtick)
                lines.append(f'<text x="{x:.2f}" y="{panel_top+panel_height+20:.2f}" text-anchor="middle" class="small">{label}</text>')
        for key, color, dash in (
            ("sigma_measured_gain_db", "#1665a7", ""),
            ("sigma_expected_gain_db", "#d1495b", ' stroke-dasharray="8 5"'),
            ("openmha_gain_db", "#2a9d5b", ' stroke-dasharray="3 4"'),
        ):
            valid = [row for row in selected if str(row[key]) != ""]
            if not valid:
                continue
            points = " ".join(
                f'{xcoord(float(row["frequency_hz"])):.2f},{ycoord(float(row[key]), panel):.2f}'
                for row in valid
            )
            lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.2"{dash}/>')
        lines += [
            f'<text x="{left+8}" y="{panel_top+20:.2f}" class="label" font-weight="700">{level} dB SPL equivalente</text>',
            f'<text x="24" y="{panel_top+panel_height/2:.2f}" class="label" transform="rotate(-90 24 {panel_top+panel_height/2:.2f})" text-anchor="middle">Ganho (dB)</text>',
        ]
    lines += [
        f'<text x="{width/2}" y="{height-15}" text-anchor="middle" class="label">Frequência (Hz)</text>',
        '<line x1="735" y1="20" x2="775" y2="20" stroke="#1665a7" stroke-width="3"/><text x="783" y="25" class="small">Sigma medido</text>',
        '<line x1="735" y1="39" x2="775" y2="39" stroke="#d1495b" stroke-width="3" stroke-dasharray="8 5"/><text x="783" y="44" class="small">Sigma esperado</text>',
        '<line x1="950" y1="20" x2="990" y2="20" stroke="#2a9d5b" stroke-width="3" stroke-dasharray="3 4"/><text x="998" y="25" class="small">openMHA CEC1</text>',
        '</svg>',
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    config = load_json(CONFIG_PATH)
    profiles = [str(value) for value in config["profiles"]]
    levels = [int(value) for value in config["levels_db_spl"]]
    manifest = load_csv(CAMPAIGN / "CAMPAIGN_MEASUREMENT_MANIFEST.csv")
    missing = [
        row["text_path"]
        for row in manifest
        if not (CAMPAIGN / row["text_path"]).is_file()
    ]
    if missing:
        print(f"Campaign is not complete: {len(missing)} REW text exports missing.")
        for value in missing:
            print(f"MISSING {value}")
        raise SystemExit(2)

    expected = load_csv(
        CAMPAIGN / "expected" / "sigma" / "sigma_expected_all_profiles.csv"
    )
    openmha_path = (
        CAMPAIGN / "expected" / "openmha" / "openmha_reference_all_profiles.csv"
    )
    openmha_rows = load_csv(openmha_path) if openmha_path.is_file() else []
    openmha_lookup: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}
    for profile in profiles:
        for level in levels:
            selected = [
                row for row in openmha_rows
                if row["profile"] == profile and int(row["level_db_spl"]) == level
            ]
            if selected:
                openmha_lookup[(profile, level)] = (
                    np.asarray([float(row["frequency_hz"]) for row in selected]),
                    np.asarray([float(row["calibrated_gain_db"]) for row in selected]),
                )

    unity = {}
    integrity = []
    for level in levels:
        row = next(
            item for item in manifest
            if item["state"] == "unity" and int(item["level_db_spl"]) == level
        )
        frequency, magnitude, metadata = read_rew(CAMPAIGN / row["text_path"])
        unity[level] = (frequency, magnitude)
        integrity.append({
            "file": row["text_path"],
            "format": metadata["format"],
            "measurement": metadata["measurement"],
            "smoothing": metadata["smoothing"],
            "status": "PASS" if "1M Log Swept Sine" in metadata["format"] and metadata["smoothing"] == "None" else "REVIEW",
        })

    processed = []
    metrics = []
    total_width = float(
        config["comparison"]["local_median_total_octave_width"]
    )
    for profile in profiles:
        profile_rows = []
        for level in levels:
            row = next(
                item for item in manifest
                if item["profile"] == profile and int(item["level_db_spl"]) == level
            )
            frequency, magnitude, metadata = read_rew(CAMPAIGN / row["text_path"])
            integrity.append({
                "file": row["text_path"],
                "format": metadata["format"],
                "measurement": metadata["measurement"],
                "smoothing": metadata["smoothing"],
                "status": "PASS" if "1M Log Swept Sine" in metadata["format"] and metadata["smoothing"] == "None" else "REVIEW",
            })
            unity_frequency, unity_magnitude = unity[level]
            measured_raw = magnitude - np.interp(frequency, unity_frequency, unity_magnitude)
            expected_selected = [
                value for value in expected
                if value["profile"] == profile and int(value["level_db_spl"]) == level
            ]
            grid = np.asarray([float(value["frequency_hz"]) for value in expected_selected])
            predicted = np.asarray([
                float(value["sigma_expected_recombined_gain_db"])
                for value in expected_selected
            ])
            measured = np.asarray([
                local_median(frequency, measured_raw, value, total_width)
                for value in grid
            ])
            if (profile, level) in openmha_lookup:
                mha_frequency, mha_gain = openmha_lookup[(profile, level)]
                mha = np.interp(grid, mha_frequency, mha_gain)
            else:
                mha = np.full_like(grid, np.nan)
            for freq, actual, model, mha_value in zip(grid, measured, predicted, mha):
                output = {
                    "profile": profile,
                    "level_db_spl": level,
                    "frequency_hz": f"{freq:.9f}",
                    "sigma_measured_gain_db": f"{actual:.9f}",
                    "sigma_expected_gain_db": f"{model:.9f}",
                    "sigma_measured_minus_expected_db": f"{actual-model:.9f}",
                    "openmha_gain_db": "" if np.isnan(mha_value) else f"{mha_value:.9f}",
                    "sigma_measured_minus_openmha_db": "" if np.isnan(mha_value) else f"{actual-mha_value:.9f}",
                }
                profile_rows.append(output)
                processed.append(output)
            useful = (grid >= 150.0) & (grid <= 9000.0)
            error = np.abs(measured[useful] - predicted[useful])
            metrics.append({
                "profile": profile,
                "level_db_spl": level,
                "sigma_model_median_abs_error_db": f"{np.median(error):.6f}",
                "sigma_model_p95_abs_error_db": f"{np.quantile(error, 0.95):.6f}",
                "sigma_model_max_abs_error_db": f"{np.max(error):.6f}",
                "sigma_openmha_median_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.median(np.abs(measured[useful]-mha[useful])):.6f}",
                "sigma_openmha_p95_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.quantile(np.abs(measured[useful]-mha[useful]),0.95):.6f}",
                "sigma_openmha_max_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.max(np.abs(measured[useful]-mha[useful])):.6f}",
                "sigma_expected_openmha_median_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.median(np.abs(predicted[useful]-mha[useful])):.6f}",
                "sigma_expected_openmha_p95_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.quantile(np.abs(predicted[useful]-mha[useful]),0.95):.6f}",
                "sigma_expected_openmha_max_abs_difference_db": "" if np.all(np.isnan(mha)) else f"{np.max(np.abs(predicted[useful]-mha[useful])):.6f}",
            })
        profile_svg(
            profile,
            levels,
            profile_rows,
            CAMPAIGN / "figures" / f"{profile}_comparison.svg",
        )

    write_csv(CAMPAIGN / "processed" / "sigma_measured_curves.csv", processed)
    write_csv(CAMPAIGN / "processed" / "comparison_metrics.csv", metrics)
    write_csv(CAMPAIGN / "processed" / "rew_export_integrity.csv", integrity)
    integrity_review = sum(row["status"] != "PASS" for row in integrity)
    report = [
        "# Resultado da campanha de prescrições",
        "",
        "Este relatório foi gerado automaticamente. As curvas usam ganho relativo `prescrição - unity`, de modo que a atenuação de saída de -19,875 dB aplicada igualmente às duas condições cancela na análise.",
        "",
        f"- Perfis processados: {len(profiles)}",
        f"- Níveis por perfil: {', '.join(str(value) for value in levels)} dB SPL equivalentes",
        f"- Baseline openMHA CEC1: {'presente' if openmha_rows else 'ainda não gerado'}",
        "- Métricas: 150 Hz a 9 kHz, magnitude, mediana local total de 1/48 de oitava",
        f"- Integridade dos exports REW: {len(integrity)-integrity_review} PASS, {integrity_review} REVIEW",
        "- O baseline openMHA preserva a calibração de saída e o soft clip da configuração CEC1; diferenças nas prescrições severas podem incluir o efeito desse estágio, ausente no Sigma atual.",
        "",
        "## Métricas por perfil e nível",
        "",
        "| Perfil | Nível | Mediana medido–modelo | P95 medido–modelo | Mediana medido–openMHA | P95 medido–openMHA | Mediana modelo–openMHA |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics:
        report.append(
            "| {profile} | {level_db_spl} dB | {sigma_model_median_abs_error_db} | "
            "{sigma_model_p95_abs_error_db} | {sigma_openmha_median_abs_difference_db} | "
            "{sigma_openmha_p95_abs_difference_db} | "
            "{sigma_expected_openmha_median_abs_difference_db} |".format(**row)
        )
    report += [
        "",
        "Todos os valores da tabela são diferenças absolutas em dB. Consulte `processed/comparison_metrics.csv` para máximos e métricas completas, `processed/rew_export_integrity.csv` para a auditoria dos exports e `figures/` para as figuras por perfil.",
        "",
    ]
    report_path = CAMPAIGN / "reports" / "CAMPAIGN_RESULT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Processed {len(processed)} curve points and wrote {len(metrics)} metric rows")


if __name__ == "__main__":
    main()
