#!/usr/bin/env python3
"""Process and plot the ADAU1787 REW power-supply comparison.

The script treats the REW text exports as immutable input, validates that all
nine expected measurements are present, writes tidy processed data, and makes
shared-scale comparison figures. Plotting uses an energy mean in 1/24-octave
bands; full-resolution REW values remain available in the compressed CSV.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


SUPPLIES = {
    "EVAL": ("eval_onboard", "Reguladores da EVAL", "#2F3B52", "-"),
    "VDD": ("tiresias_vdd", "VDD do Tiresias", "#0072B2", "--"),
    "AVDD": ("tiresias_avdd", "AVDD do Tiresias", "#D55E00", "-."),
}

INPUTS = {
    "noise": ("no_input", "Sem entrada"),
    "-10dB": ("minus10_dbv", "Entrada −10 dBV"),
    "-6dB": ("minus6_dbv", "Entrada −6 dBV"),
}

INPUT_ORDER = ["no_input", "minus10_dbv", "minus6_dbv"]
SUPPLY_ORDER = ["eval_onboard", "tiresias_vdd", "tiresias_avdd"]
INPUT_LABEL = {value[0]: value[1] for value in INPUTS.values()}
SUPPLY_LABEL = {value[0]: value[1] for value in SUPPLIES.values()}
STYLE = {value[0]: (value[2], value[3]) for value in SUPPLIES.values()}


@dataclass(frozen=True)
class Measurement:
    path: Path
    supply: str
    input_condition: str
    rew_name: str
    rew_version: str
    dated: str
    format_description: str
    smoothing: str
    frequency_step_hz: float
    input_rms_dbfs: float
    input_rms_22_22k_unweighted_dbfs: float
    frequency_hz: np.ndarray
    level_dbv: np.ndarray


def header_value(header: str, label: str, default: str = "") -> str:
    match = re.search(rf"^\* {re.escape(label)}:\s*(.+)$", header, re.MULTILINE)
    return match.group(1).strip() if match else default


def parse_measurement(path: Path) -> Measurement:
    text = path.read_text(encoding="utf-8", errors="replace")
    header = "\n".join(line for line in text.splitlines() if line.startswith("*"))

    match = re.fullmatch(r"(EVAL|VDD|AVDD)\s*-?\s*(noise|-10dB|-6dB)", path.stem)
    if not match:
        raise ValueError(f"Unrecognised REW filename: {path.name}")
    supply_key, input_key = match.groups()
    supply = SUPPLIES[supply_key][0]
    input_condition = INPUTS[input_key][0]

    version_match = re.search(r"measured by REW\s+([^\s]+)", header)
    note = header_value(header, "Note")
    rms_match = re.search(r"Input RMS\s+(-?\d+(?:\.\d+)?)\s+dBFS", note)
    band_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s+dBFS\s+22\s*-\s*22k\s+UNW", note
    )

    data = np.loadtxt(path, comments="*")
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"Expected two numeric columns in {path}")
    frequency_hz, level_dbv = data.T
    if not np.all(np.diff(frequency_hz) > 0):
        raise ValueError(f"Frequency axis is not strictly increasing in {path}")

    return Measurement(
        path=path,
        supply=supply,
        input_condition=input_condition,
        rew_name=header_value(header, "Measurement", path.stem),
        rew_version=version_match.group(1) if version_match else "unknown",
        dated=header_value(header, "Dated"),
        format_description=header_value(header, "Format"),
        smoothing=header_value(header, "Smoothing", "unknown"),
        frequency_step_hz=float(header_value(header, "Frequency Step", "nan").split()[0]),
        input_rms_dbfs=float(rms_match.group(1)) if rms_match else math.nan,
        input_rms_22_22k_unweighted_dbfs=(
            float(band_match.group(1)) if band_match else math.nan
        ),
        frequency_hz=frequency_hz,
        level_dbv=level_dbv,
    )


def octave_power_mean(
    frequency_hz: np.ndarray,
    level_dbv: np.ndarray,
    bands_per_octave: int = 24,
    low_hz: float = 20.0,
    high_hz: float = 22_000.0,
) -> tuple[np.ndarray, np.ndarray]:
    count = int(np.ceil(np.log2(high_hz / low_hz) * bands_per_octave))
    edges = low_hz * 2.0 ** (np.arange(count + 1) / bands_per_octave)
    edges[-1] = max(edges[-1], high_hz)
    centres = np.sqrt(edges[:-1] * edges[1:])
    result = np.full(count, np.nan)
    linear_power = 10.0 ** (level_dbv / 10.0)
    indices = np.searchsorted(frequency_hz, edges)
    for index, (start, stop) in enumerate(zip(indices[:-1], indices[1:])):
        if stop > start:
            result[index] = 10.0 * np.log10(np.mean(linear_power[start:stop]))
    valid = np.isfinite(result) & (centres <= high_hz)
    return centres[valid], result[valid]


def _dash_array(line_style: str) -> str:
    return {"-": "", "--": "9 6", "-.": "11 5 2 5"}[line_style]


def _tick_step(span: float) -> float:
    if span <= 20:
        return 5
    if span <= 60:
        return 10
    return 20


def render_facets_svg(
    stem: Path,
    title: str,
    panels: list[tuple[str, list[dict[str, object]]]],
    y_limits: tuple[float, float],
    y_label: str,
    legend: list[tuple[str, str, str]],
) -> None:
    """Render publication-ready shared-scale facets without plotting dependencies."""
    width = 1200
    left, right = 112, 36
    top, bottom = 112, 110
    panel_height = 236 if len(panels) >= 3 else 285
    panel_gap = 54
    height = top + bottom + len(panels) * panel_height + (len(panels) - 1) * panel_gap
    plot_width = width - left - right
    y_min, y_max = y_limits
    x_min, x_max = 20.0, 22_000.0
    x_ticks = [20, 50, 100, 200, 500, 1_000, 2_000, 5_000, 10_000, 20_000]
    x_labels = ["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"]
    y_step = _tick_step(y_max - y_min)
    y_ticks = np.arange(
        math.ceil(y_min / y_step) * y_step,
        math.floor(y_max / y_step) * y_step + y_step / 2,
        y_step,
    )

    def sx(value: float) -> float:
        return left + (math.log10(value) - math.log10(x_min)) / (
            math.log10(x_max) - math.log10(x_min)
        ) * plot_width

    def sy(value: float, panel_top: float) -> float:
        return panel_top + (y_max - value) / (y_max - y_min) * panel_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;fill:#18212F}",
        ".title{font-size:23px;font-weight:600}.panel{font-size:16px;font-weight:600}",
        ".axis{font-size:13px}.legend{font-size:14px}.footer{font-size:11px;fill:#586173}",
        ".grid-major{stroke:#D4D9E2;stroke-width:1}.grid-minor{stroke:#E9ECF1;stroke-width:.7}",
        ".axis-line{stroke:#4B5563;stroke-width:1.1}",
        "</style>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text x="{left}" y="36" class="title">{html.escape(title)}</text>',
    ]

    legend_x = left
    for label, colour, dash in legend:
        dash_attr = f' stroke-dasharray="{_dash_array(dash)}"' if dash != "-" else ""
        parts.append(
            f'<line x1="{legend_x}" y1="72" x2="{legend_x + 38}" y2="72" '
            f'stroke="{colour}" stroke-width="3"{dash_attr}/>'
        )
        parts.append(
            f'<text x="{legend_x + 48}" y="77" class="legend">{html.escape(label)}</text>'
        )
        legend_x += 48 + 8.1 * len(label) + 44

    for panel_index, (panel_label, series) in enumerate(panels):
        panel_top = top + panel_index * (panel_height + panel_gap)
        clip_id = f"clip-{panel_index}"
        parts.append(
            f'<clipPath id="{clip_id}"><rect x="{left}" y="{panel_top}" '
            f'width="{plot_width}" height="{panel_height}"/></clipPath>'
        )
        parts.append(
            f'<text x="{left}" y="{panel_top - 14}" class="panel">{html.escape(panel_label)}</text>'
        )

        for x_tick, x_label in zip(x_ticks, x_labels):
            x = sx(x_tick)
            grid_class = "grid-major" if x_tick in (20, 100, 1_000, 10_000) else "grid-minor"
            parts.append(
                f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" '
                f'y2="{panel_top + panel_height}" class="{grid_class}"/>'
            )
            if panel_index == len(panels) - 1:
                parts.append(
                    f'<text x="{x:.2f}" y="{panel_top + panel_height + 24}" '
                    f'text-anchor="middle" class="axis">{x_label}</text>'
                )

        for y_tick in y_ticks:
            y = sy(float(y_tick), panel_top)
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" '
                f'y2="{y:.2f}" class="grid-major"/>'
            )
            parts.append(
                f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
                f'class="axis">{y_tick:g}</text>'
            )

        parts.append(
            f'<line x1="{left}" y1="{panel_top + panel_height}" x2="{left + plot_width}" '
            f'y2="{panel_top + panel_height}" class="axis-line"/>'
        )
        parts.append(
            f'<line x1="{left}" y1="{panel_top}" x2="{left}" '
            f'y2="{panel_top + panel_height}" class="axis-line"/>'
        )
        parts.append(
            f'<text x="28" y="{panel_top + panel_height / 2}" text-anchor="middle" '
            f'transform="rotate(-90 28 {panel_top + panel_height / 2})" class="axis">'
            f'{html.escape(y_label)}</text>'
        )

        for item in series:
            frequency = np.asarray(item["frequency_hz"])
            level = np.asarray(item["level"])
            valid = np.isfinite(frequency) & np.isfinite(level) & (frequency >= x_min) & (frequency <= x_max)
            points = [f"{sx(float(x)):.2f},{sy(float(y), panel_top):.2f}" for x, y in zip(frequency[valid], level[valid])]
            if not points:
                continue
            dash = str(item["dash"])
            dash_attr = f' stroke-dasharray="{_dash_array(dash)}"' if dash != "-" else ""
            parts.append(
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{item["colour"]}" '
                f'stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" '
                f'clip-path="url(#{clip_id})"{dash_attr}/>'
            )

    final_panel_top = top + (len(panels) - 1) * (panel_height + panel_gap)
    parts.append(
        f'<text x="{left + plot_width / 2}" y="{final_panel_top + panel_height + 48}" '
        f'text-anchor="middle" class="axis">Frequência (Hz)</text>'
    )
    parts.append(
        f'<text x="{width / 2}" y="{height - 18}" text-anchor="middle" class="footer">'
        "REW V5.31.3 · 131072 pontos · Hann · 32 médias · média energética em 1/24 de oitava"
        "</text>"
    )
    parts.append("</svg>")
    svg_path = stem.with_suffix(".svg")
    svg_path.write_text("\n".join(parts), encoding="utf-8")

    converter = shutil.which("rsvg-convert")
    if converter:
        subprocess.run(
            [converter, "-f", "png", "-o", str(stem.with_suffix(".png")), str(svg_path)],
            check=True,
        )
        subprocess.run(
            [converter, "-f", "pdf", "-o", str(stem.with_suffix(".pdf")), str(svg_path)],
            check=True,
        )


def write_full_resolution_csv(measurements: list[Measurement], destination: Path) -> None:
    with gzip.open(destination, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "frequency_hz",
                "level_dbv",
                "supply",
                "input_condition",
                "rew_measurement",
                "source_file",
            ]
        )
        for item in measurements:
            writer.writerows(
                (
                    f"{frequency_hz:.6f}",
                    f"{level_dbv:.6f}",
                    item.supply,
                    item.input_condition,
                    item.rew_name,
                    item.path.name,
                )
                for frequency_hz, level_dbv in zip(item.frequency_hz, item.level_dbv)
            )


def write_dict_rows(rows: list[dict[str, object]], destination: Path) -> None:
    if not rows:
        raise ValueError(f"No rows to write to {destination}")
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def checksum_manifest(raw_dir: Path, destination: Path) -> None:
    lines = []
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(raw_dir)}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "experiment_dir",
        nargs="?",
        type=Path,
        default=Path("docs/measurements/adau1787_power_supply_2026-08-07"),
    )
    args = parser.parse_args()
    experiment_dir = args.experiment_dir.resolve()
    exports_dir = experiment_dir / "raw" / "exports"
    processed_dir = experiment_dir / "processed"
    figures_dir = experiment_dir / "figures"
    processed_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    measurements = [parse_measurement(path) for path in sorted(exports_dir.glob("*.txt"))]
    expected = {(supply, input_) for supply in SUPPLY_ORDER for input_ in INPUT_ORDER}
    observed = {(item.supply, item.input_condition) for item in measurements}
    if observed != expected or len(measurements) != 9:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(
            f"Expected exactly nine measurements; missing={missing}, extra={extra}, "
            f"count={len(measurements)}"
        )

    reference_axis = measurements[0].frequency_hz
    for item in measurements[1:]:
        if not np.array_equal(reference_axis, item.frequency_hz):
            raise RuntimeError(f"Frequency grid mismatch: {item.path.name}")

    write_full_resolution_csv(
        measurements, processed_dir / "spectra_full_resolution.csv.gz"
    )

    smooth_rows: list[dict[str, object]] = []
    smooth_lookup: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    summary_rows = []
    for item in measurements:
        frequency_hz, level_dbv = octave_power_mean(item.frequency_hz, item.level_dbv)
        smooth_lookup[(item.supply, item.input_condition)] = (frequency_hz, level_dbv)
        smooth_rows.extend(
            {
                "frequency_hz": f"{frequency:.6f}",
                "level_dbv_power_mean": f"{level:.6f}",
                "supply": item.supply,
                "input_condition": item.input_condition,
            }
            for frequency, level in zip(frequency_hz, level_dbv)
        )

        audio_band = (item.frequency_hz >= 20) & (item.frequency_hz <= 22_000)
        tone_band = (item.frequency_hz >= 990) & (item.frequency_hz <= 1_010)
        peak_index = int(np.argmax(item.level_dbv[tone_band]))
        tone_frequencies = item.frequency_hz[tone_band]
        tone_levels = item.level_dbv[tone_band]
        summary_rows.append(
            {
                "supply": item.supply,
                "input_condition": item.input_condition,
                "rew_measurement": item.rew_name,
                "rew_version": item.rew_version,
                "dated": item.dated,
                "format": item.format_description,
                "smoothing": item.smoothing,
                "frequency_step_hz": item.frequency_step_hz,
                "input_rms_dbfs": item.input_rms_dbfs,
                "input_rms_22_22k_unweighted_dbfs": item.input_rms_22_22k_unweighted_dbfs,
                "peak_near_1khz_frequency_hz": tone_frequencies[peak_index],
                "peak_near_1khz_level_dbv": tone_levels[peak_index],
                "median_bin_level_20_22k_dbv": float(np.median(item.level_dbv[audio_band])),
                "p95_bin_level_20_22k_dbv": float(np.percentile(item.level_dbv[audio_band], 95)),
                "source_file": item.path.name,
            }
        )

    write_dict_rows(smooth_rows, processed_dir / "spectra_1_24_octave.csv")
    summary_rows.sort(
        key=lambda row: (
            INPUT_ORDER.index(str(row["input_condition"])),
            SUPPLY_ORDER.index(str(row["supply"])),
        )
    )
    write_dict_rows(summary_rows, processed_dir / "summary.csv")
    checksum_manifest(experiment_dir / "raw", experiment_dir / "SHA256SUMS.txt")

    def supply_series(input_condition: str) -> list[dict[str, object]]:
        result = []
        for supply in SUPPLY_ORDER:
            frequency_hz, level_dbv = smooth_lookup[(supply, input_condition)]
            colour, line_style = STYLE[supply]
            result.append(
                {
                    "frequency_hz": frequency_hz,
                    "level": level_dbv,
                    "colour": colour,
                    "dash": line_style,
                }
            )
        return result

    supply_legend = [
        (SUPPLY_LABEL[supply], STYLE[supply][0], STYLE[supply][1])
        for supply in SUPPLY_ORDER
    ]
    render_facets_svg(
        figures_dir / "01_all_inputs_supply_overlay",
        "ADAU1787 — comparação das três alimentações",
        [(INPUT_LABEL[input_condition], supply_series(input_condition)) for input_condition in INPUT_ORDER],
        (-135, 0),
        "Magnitude espectral (dBV)",
        supply_legend,
    )

    values = [smooth_lookup[(supply, "no_input")][1] for supply in SUPPLY_ORDER]
    all_values = np.concatenate(values)
    lower = float(5 * np.floor(np.nanpercentile(all_values, 1) / 5))
    upper = float(5 * np.ceil(np.nanpercentile(all_values, 99.7) / 5))
    render_facets_svg(
        figures_dir / "02_no_input_supply_comparison",
        "Sem entrada — detalhe do piso de ruído",
        [("Sem entrada", supply_series("no_input"))],
        (lower, upper),
        "Magnitude espectral (dBV)",
        supply_legend,
    )

    render_facets_svg(
        figures_dir / "03_signal_supply_comparison",
        "Espectros com tom de 1 kHz",
        [
            (INPUT_LABEL[input_condition], supply_series(input_condition))
            for input_condition in ["minus10_dbv", "minus6_dbv"]
        ],
        (-135, 0),
        "Magnitude espectral (dBV)",
        supply_legend,
    )

    delta_series = []
    for input_condition in INPUT_ORDER:
        reference_frequency, reference_level = smooth_lookup[("eval_onboard", input_condition)]
        for supply in ["tiresias_vdd", "tiresias_avdd"]:
            frequency_hz, level_dbv = smooth_lookup[(supply, input_condition)]
            if not np.array_equal(reference_frequency, frequency_hz):
                raise RuntimeError("Smoothed frequency-grid mismatch")
            delta_series.append(level_dbv - reference_level)
    robust_limit = float(np.nanpercentile(np.abs(np.concatenate(delta_series)), 98))
    delta_limit = min(20.0, max(5.0, math.ceil(robust_limit / 2) * 2.0))

    delta_panels = []
    for input_condition in INPUT_ORDER:
        reference_frequency, reference_level = smooth_lookup[("eval_onboard", input_condition)]
        series = []
        for supply in ["tiresias_vdd", "tiresias_avdd"]:
            frequency_hz, level_dbv = smooth_lookup[(supply, input_condition)]
            colour, line_style = STYLE[supply]
            series.append(
                {
                    "frequency_hz": frequency_hz,
                    "level": level_dbv - reference_level,
                    "colour": colour,
                    "dash": line_style,
                }
            )
        delta_panels.append((INPUT_LABEL[input_condition], series))
    delta_legend = [
        (f"{SUPPLY_LABEL[supply]} − EVAL", STYLE[supply][0], STYLE[supply][1])
        for supply in ["tiresias_vdd", "tiresias_avdd"]
    ]
    render_facets_svg(
        figures_dir / "04_delta_vs_eval",
        "Diferença espectral relativa aos reguladores da EVAL",
        delta_panels,
        (-delta_limit, delta_limit),
        "Diferença (dB)",
        delta_legend,
    )

    print(f"Processed {len(measurements)} measurements from {exports_dir}")
    print(f"Figures: {figures_dir}")
    print(f"Processed data: {processed_dir}")


if __name__ == "__main__":
    main()
