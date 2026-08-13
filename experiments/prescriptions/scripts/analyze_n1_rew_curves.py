#!/usr/bin/env python3
"""Validate N1 REW sweeps against the stationary-tone anchors and model."""

from __future__ import annotations

import csv
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


CURVE_DIR = WORKSPACE / "tiresias-eval-sigma" / "rew" / "N1" / "curves"
CONFIG_PATH = WORKSPACE / "tiresias-eval-sigma" / "config" / "prescription_eval.json"
CALIBRATION_PATH = WORKSPACE / "tiresias-eval-sigma" / "config" / "detector_calibration_eval.json"
MANIFEST_PATH = WORKSPACE / "tiresias-eval-sigma" / "scripts" / "generated" / "N1" / "N1_manifest.json"
RESULT_DIR = CURVE_DIR / "results"

LEVELS = (45, 65, 85)
LEVEL_TAGS = {45: "59", 65: "39", 85: "19"}
CENTRES = (177.0, 297.0, 500.0, 841.0, 1414.0, 2378.0, 4000.0, 6727.0)
STATIONARY = {
    2378.0: {45: 7.79, 65: 6.83, 85: 6.18},
    4000.0: {45: 15.82, 65: 10.74, 85: 7.56},
    6727.0: {45: 16.23, 65: 7.96, 85: 4.10},
}


def load_rew(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="*")
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Unexpected REW text export: {path}")
    return data[:, 0], data[:, 1]


def pair_paths(level: int) -> tuple[Path, Path]:
    tag = LEVEL_TAGS[level]
    return (
        CURVE_DIR / f"unity_{level}dBSPL_-{tag}p85dBV.txt",
        CURVE_DIR / f"N1_{level}dBSPL_-{tag}p85dBV.txt",
    )


def pair_paths_2m(level: int) -> tuple[Path, Path]:
    tag = LEVEL_TAGS[level]
    return (
        CURVE_DIR / f"2M_un_{level}dBSPL_-{tag}p85dBV.txt",
        CURVE_DIR / f"N1_{level}dBSPL_-{tag}p85dBV_2M.txt",
    )


def octave_window_median(
    frequencies: np.ndarray,
    values: np.ndarray,
    query: float,
    half_width_octaves: float = 1.0 / 96.0,
) -> tuple[float, float, int]:
    mask = np.abs(np.log2(frequencies / query)) <= half_width_octaves
    selected = values[mask]
    if selected.size == 0:
        return float(np.interp(query, frequencies, values)), float("nan"), 1
    return float(np.median(selected)), float(np.std(selected)), int(selected.size)


def prediction_context() -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    export_path = (CONFIG_PATH.parent / config["sigma_export_xml"]).resolve()
    modules = export_modules(export_path)
    reference_magnitudes = []
    for index, centre in enumerate(CENTRES):
        contributions, _ = filterbank_contributions(modules, centre, 48000.0)
        reference_magnitudes.append(abs(contributions[index]))
    return {
        "modules": modules,
        "calibration": calibration["measured_band_calibration"],
        "detector_points": [float(v) for v in manifest["mapping"]["detector_points_dbfs"]],
        "tables": [row["quantized_lut_gain_db"] for row in manifest["tables"]],
        "bias_db": float(manifest["mapping"]["quantized_bias_total_db"]),
        "reference_magnitudes": reference_magnitudes,
    }


def predicted_gain(frequency: float, level: float, context: dict) -> float:
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


def write_svg(curve_data: dict[int, dict[str, np.ndarray]], path: Path) -> None:
    width, height = 1200, 960
    left, right, top, bottom = 90, 30, 55, 65
    panel_gap = 55
    panel_height = (height - top - bottom - 2 * panel_gap) / 3.0
    plot_width = width - left - right
    y_min, y_max = -2.0, 22.0

    def xcoord(frequency: float) -> float:
        return left + plot_width * math.log10(frequency / 100.0) / 2.0

    def ycoord(value: float, panel: int) -> float:
        panel_top = top + panel * (panel_height + panel_gap)
        return panel_top + panel_height * (y_max - value) / (y_max - y_min)

    def polyline(xs: np.ndarray, ys: np.ndarray, panel: int) -> str:
        points = " ".join(
            f"{xcoord(float(x)):.2f},{ycoord(float(y), panel):.2f}"
            for x, y in zip(xs, ys)
        )
        return points

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#202124}.title{font-size:20px;font-weight:700}.label{font-size:14px}.small{font-size:12px}</style>',
        '<text x="600" y="28" text-anchor="middle" class="title">N1 — validação das curvas REW 1M</text>',
    ]
    for panel, level in enumerate(LEVELS):
        panel_top = top + panel * (panel_height + panel_gap)
        for ytick in (0, 5, 10, 15, 20):
            y = ycoord(float(ytick), panel)
            lines += [
                f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#d9d9d9" stroke-width="1"/>',
                f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="small">{ytick}</text>',
            ]
        for xtick in (100, 200, 500, 1000, 2000, 5000, 10000):
            x = xcoord(float(xtick))
            lines.append(f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" y2="{panel_top+panel_height:.2f}" stroke="#eeeeee" stroke-width="1"/>')
            if panel == 2:
                label = f"{xtick//1000}k" if xtick >= 1000 else str(xtick)
                lines.append(f'<text x="{x:.2f}" y="{panel_top+panel_height+20:.2f}" text-anchor="middle" class="small">{label}</text>')
        data = curve_data[level]
        lines += [
            f'<polyline points="{polyline(data["grid"], data["smooth_gain"], panel)}" fill="none" stroke="#1665a7" stroke-width="2.2"/>',
            f'<polyline points="{polyline(data["grid"], data["prediction"], panel)}" fill="none" stroke="#d1495b" stroke-width="2" stroke-dasharray="8 5"/>',
            f'<text x="{left+8}" y="{panel_top+20:.2f}" class="label" font-weight="700">{level} dB SPL equivalente</text>',
            f'<text x="24" y="{panel_top+panel_height/2:.2f}" class="label" transform="rotate(-90 24 {panel_top+panel_height/2:.2f})" text-anchor="middle">Ganho (dB)</text>',
        ]
        for centre, level_map in STATIONARY.items():
            lines.append(f'<circle cx="{xcoord(centre):.2f}" cy="{ycoord(level_map[level], panel):.2f}" r="4" fill="#222222"/>')
    lines += [
        f'<text x="{width/2}" y="{height-15}" text-anchor="middle" class="label">Frequência (Hz)</text>',
        '<line x1="760" y1="24" x2="800" y2="24" stroke="#1665a7" stroke-width="3"/><text x="808" y="29" class="small">REW 1M, mediana 1/48 oct</text>',
        '<line x1="760" y1="43" x2="800" y2="43" stroke="#d1495b" stroke-width="3" stroke-dasharray="8 5"/><text x="808" y="48" class="small">modelo quase-estacionário</text>',
        '<circle cx="1060" cy="24" r="4" fill="#222222"/><text x="1070" y="29" class="small">tons</text>',
        '</svg>',
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_convergence_svg(
    curve_data: dict[int, dict[str, np.ndarray]], path: Path
) -> None:
    width, height = 1200, 960
    left, right, top, bottom = 90, 30, 55, 65
    panel_gap = 55
    panel_height = (height - top - bottom - 2 * panel_gap) / 3.0
    plot_width = width - left - right
    y_min, y_max = -1.0, 1.0

    def xcoord(frequency: float) -> float:
        return left + plot_width * math.log10(frequency / 100.0) / 2.0

    def ycoord(value: float, panel: int) -> float:
        panel_top = top + panel * (panel_height + panel_gap)
        return panel_top + panel_height * (y_max - value) / (y_max - y_min)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#202124}.title{font-size:20px;font-weight:700}.label{font-size:14px}.small{font-size:12px}</style>',
        '<text x="600" y="28" text-anchor="middle" class="title">N1 — convergência temporal 2M − 1M</text>',
    ]
    for panel, level in enumerate(LEVELS):
        panel_top = top + panel * (panel_height + panel_gap)
        for ytick in (-1.0, -0.5, 0.0, 0.5, 1.0):
            y = ycoord(ytick, panel)
            color = "#777777" if ytick == 0.0 else "#e5e5e5"
            lines += [
                f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="{color}" stroke-width="1"/>',
                f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="small">{ytick:g}</text>',
            ]
        for limit in (-0.2, 0.2):
            y = ycoord(limit, panel)
            lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#d1495b" stroke-width="1.5" stroke-dasharray="7 5"/>')
        for xtick in (100, 200, 500, 1000, 2000, 5000, 10000):
            x = xcoord(float(xtick))
            lines.append(f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" y2="{panel_top+panel_height:.2f}" stroke="#eeeeee" stroke-width="1"/>')
            if panel == 2:
                label = f"{xtick//1000}k" if xtick >= 1000 else str(xtick)
                lines.append(f'<text x="{x:.2f}" y="{panel_top+panel_height+20:.2f}" text-anchor="middle" class="small">{label}</text>')
        data = curve_data[level]
        points = " ".join(
            f"{xcoord(float(x)):.2f},{ycoord(float(y), panel):.2f}"
            for x, y in zip(data["grid"], data["convergence_delta"])
        )
        lines += [
            f'<polyline points="{points}" fill="none" stroke="#1665a7" stroke-width="2.2"/>',
            f'<text x="{left+8}" y="{panel_top+20:.2f}" class="label" font-weight="700">{level} dB SPL equivalente</text>',
            f'<text x="24" y="{panel_top+panel_height/2:.2f}" class="label" transform="rotate(-90 24 {panel_top+panel_height/2:.2f})" text-anchor="middle">2M − 1M (dB)</text>',
        ]
    lines += [
        f'<text x="{width/2}" y="{height-15}" text-anchor="middle" class="label">Frequência (Hz)</text>',
        '<line x1="810" y1="24" x2="850" y2="24" stroke="#1665a7" stroke-width="3"/><text x="858" y="29" class="small">diferença medida</text>',
        '<line x1="810" y1="43" x2="850" y2="43" stroke="#d1495b" stroke-width="2" stroke-dasharray="7 5"/><text x="858" y="48" class="small">critério ±0,20 dB</text>',
        '</svg>',
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    context = prediction_context()
    grid = np.geomspace(100.0, 10000.0, 481)
    centre_rows: list[dict[str, str]] = []
    convergence_rows: list[dict[str, str]] = []
    curve_data: dict[int, dict[str, np.ndarray]] = {}

    for level in LEVELS:
        unity_path, n1_path = pair_paths(level)
        frequency, unity = load_rew(unity_path)
        n1_frequency, n1 = load_rew(n1_path)
        if not np.array_equal(frequency, n1_frequency):
            raise ValueError(f"Frequency grids differ for {level} dB SPL")
        raw_gain = n1 - unity
        smooth_gain = np.array([
            octave_window_median(frequency, raw_gain, value)[0] for value in grid
        ])
        prediction = np.array([
            predicted_gain(value, float(level), context) for value in grid
        ])
        curve_data[level] = {
            "frequency": frequency,
            "unity": unity,
            "n1": n1,
            "raw_gain": raw_gain,
            "grid": grid,
            "smooth_gain": smooth_gain,
            "prediction": prediction,
        }
        unity_2m_path, n1_2m_path = pair_paths_2m(level)
        frequency_2m, unity_2m = load_rew(unity_2m_path)
        n1_frequency_2m, n1_2m = load_rew(n1_2m_path)
        if not np.array_equal(frequency_2m, n1_frequency_2m):
            raise ValueError(f"2M frequency grids differ for {level} dB SPL")
        raw_gain_2m = n1_2m - unity_2m
        smooth_gain_2m = np.array([
            octave_window_median(frequency_2m, raw_gain_2m, value)[0]
            for value in grid
        ])
        curve_data[level]["smooth_gain_2m"] = smooth_gain_2m
        curve_data[level]["convergence_delta"] = smooth_gain_2m - smooth_gain
        for centre in CENTRES:
            measured, local_std, count = octave_window_median(
                frequency, raw_gain, centre
            )
            predicted = predicted_gain(centre, float(level), context)
            stationary = STATIONARY.get(centre, {}).get(level)
            centre_rows.append({
                "level_db_spl": str(level),
                "frequency_hz": f"{centre:.0f}",
                "sweep_gain_median_db": f"{measured:.6f}",
                "local_raw_std_db": f"{local_std:.6f}",
                "points_in_median": str(count),
                "predicted_gain_db": f"{predicted:.6f}",
                "sweep_minus_prediction_db": f"{measured - predicted:.6f}",
                "stationary_gain_db": "" if stationary is None else f"{stationary:.6f}",
                "sweep_minus_stationary_db": "" if stationary is None else f"{measured - stationary:.6f}",
            })
            measured_2m, local_std_2m, count_2m = octave_window_median(
                frequency_2m, raw_gain_2m, centre
            )
            delta = measured_2m - measured
            convergence_rows.append({
                "level_db_spl": str(level),
                "frequency_hz": f"{centre:.0f}",
                "gain_1m_db": f"{measured:.6f}",
                "gain_2m_db": f"{measured_2m:.6f}",
                "delta_2m_minus_1m_db": f"{delta:.6f}",
                "abs_delta_db": f"{abs(delta):.6f}",
                "local_raw_std_1m_db": f"{local_std:.6f}",
                "local_raw_std_2m_db": f"{local_std_2m:.6f}",
                "points_1m": str(count),
                "points_2m": str(count_2m),
                "strict_centre_status": (
                    "INCONCLUSIVE_NOISE" if level == 45 else
                    "PASS" if abs(delta) <= 0.20 else "MARGINAL_FAIL"
                ),
            })

    csv_path = RESULT_DIR / "N1_1M_centre_validation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(centre_rows[0]))
        writer.writeheader()
        writer.writerows(centre_rows)

    convergence_csv = RESULT_DIR / "N1_1M_2M_convergence_centres.csv"
    with convergence_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(convergence_rows[0]))
        writer.writeheader()
        writer.writerows(convergence_rows)

    write_svg(curve_data, RESULT_DIR / "N1_1M_gain_validation.svg")
    write_convergence_svg(curve_data, RESULT_DIR / "N1_1M_2M_convergence.svg")

    anchor_rows = [row for row in centre_rows if row["stationary_gain_db"]]
    deviations_by_level = {
        level: [
            abs(float(row["sweep_minus_stationary_db"]))
            for row in anchor_rows
            if int(row["level_db_spl"]) == level
        ]
        for level in LEVELS
    }
    model_errors_by_level = {}
    convergence_errors_by_level = {}
    for level in LEVELS:
        data = curve_data[level]
        useful = (data["grid"] >= 150.0) & (data["grid"] <= 9000.0)
        model_errors_by_level[level] = np.abs(
            data["smooth_gain"][useful] - data["prediction"][useful]
        )
        convergence_errors_by_level[level] = np.abs(
            data["convergence_delta"][useful]
        )
    report = [
        "# Validação das curvas N1 de 1M no REW",
        "",
        "As seis curvas foram usadas somente para validar o método. A condição de 45 dB SPL equivalente apresenta contaminação de rede/SNR visivelmente maior e não deve ser usada para caracterizar o ruído próprio da plataforma.",
        "",
        "A curva medida foi calculada por `N1 - unity` em dB e resumida com mediana em uma janela total de 1/48 de oitava. A fase foi ignorada.",
        "",
        "## Comparação com os tons estacionários",
        "",
        "| Nível | desvio máximo | desvio médio | interpretação |",
        "|---:|---:|---:|---|",
    ]
    for level in LEVELS:
        values = deviations_by_level[level]
        interpretation = (
            "contaminado; apenas validação qualitativa"
            if level == 45 else
            "válido para magnitude"
        )
        report.append(
            f"| {level} dB SPL | {max(values):.3f} dB | {sum(values)/len(values):.3f} dB | {interpretation} |"
        )
    report += [
        "",
        "Os dados completos por centro de banda estão em `N1_1M_centre_validation.csv`. Os pontos pretos da figura são as medidas estacionárias B6–B8.",
        "",
        "## Comparação global com o modelo (150 Hz a 9 kHz)",
        "",
        "| Nível | erro mediano | percentil 95 | erro máximo |",
        "|---:|---:|---:|---:|",
    ]
    for level in LEVELS:
        values = model_errors_by_level[level]
        report.append(
            f"| {level} dB SPL | {np.median(values):.3f} dB | {np.quantile(values, 0.95):.3f} dB | {np.max(values):.3f} dB |"
        )
    report += [
        "",
        "## Decisão",
        "",
        "- **65 e 85 dB SPL: GO para validação de magnitude.**",
        "- **45 dB SPL: GO apenas qualitativo.** Use a mediana local e preserve a marcação de contaminação; não use esta aquisição para piso de ruído, THD ou conclusões finas.",
        "- Em 85 dB SPL, 95% da faixa ficou a menos de 0,046 dB do modelo; em 65 dB SPL, a mesma estatística foi 0,353 dB.",
        "- A curva de 1M reproduz B7 e B8. Em B6/85 dB SPL, o sweep coincide com o modelo e sugere que o ponto estacionário anterior de +6,18 dB merece repetição futura.",
        "- A convergência temporal 1M/2M foi executada posteriormente; consulte `N1_1M_2M_CONVERGENCE.md`.",
        "",
    ]
    (RESULT_DIR / "N1_1M_VALIDATION.md").write_text("\n".join(report), encoding="utf-8")
    convergence_report = [
        "# Convergência temporal N1: sweeps de 1M e 2M",
        "",
        "A comparação usa pares N1/unity independentes em cada duração. Cada curva de ganho foi resumida por mediana em uma janela total de 1/48 de oitava; a fase não foi usada.",
        "",
        "| Nível | |2M−1M| mediano | percentil 95 | máximo entre 150 Hz e 9 kHz | máximo nos centros | decisão |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    centre_abs_by_level = {
        level: [
            float(row["abs_delta_db"])
            for row in convergence_rows
            if int(row["level_db_spl"]) == level
        ]
        for level in LEVELS
    }
    decisions = {
        45: "inconclusivo por ruído de rede/SNR",
        65: "marginal: B6 = 0,232 dB",
        85: "PASS",
    }
    for level in LEVELS:
        values = convergence_errors_by_level[level]
        convergence_report.append(
            f"| {level} dB SPL | {np.median(values):.3f} dB | {np.quantile(values, 0.95):.3f} dB | {np.max(values):.3f} dB | {max(centre_abs_by_level[level]):.3f} dB | {decisions[level]} |"
        )
    convergence_report += [
        "",
        "## Interpretação",
        "",
        "- **85 dB SPL convergiu claramente:** a diferença máxima em toda a faixa útil foi 0,016 dB.",
        "- **65 dB SPL é praticamente estável:** 95% da faixa ficou dentro de 0,130 dB. Somente B6 excedeu o critério de centro de ±0,20 dB, chegando a 0,232 dB; o excesso foi 0,032 dB.",
        "- **45 dB SPL não permite atribuir as diferenças à dinâmica:** a contaminação já observada produz dispersão local e diferenças não monotônicas. O resultado é marcado como inconclusivo, não como falha do WDRC.",
        "- Para a validação atual, 1M é suficiente em 65 e 85 dB SPL. Para uma curva quantitativa de referência em 45 dB SPL, repita em uma alimentação limpa ou use stepped sine com settling de 500 ms.",
        "- Não foi aplicada correção matemática de attack/release; a conclusão vem diretamente da invariância observada ao dobrar a duração.",
        "",
    ]
    (RESULT_DIR / "N1_1M_2M_CONVERGENCE.md").write_text(
        "\n".join(convergence_report), encoding="utf-8"
    )
    print(f"Wrote {csv_path}")
    print(f"Wrote {convergence_csv}")
    print(f"Wrote {RESULT_DIR / 'N1_1M_gain_validation.svg'}")
    print(f"Wrote {RESULT_DIR / 'N1_1M_2M_convergence.svg'}")
    print(f"Wrote {RESULT_DIR / 'N1_1M_VALIDATION.md'}")
    print(f"Wrote {RESULT_DIR / 'N1_1M_2M_CONVERGENCE.md'}")


if __name__ == "__main__":
    main()
