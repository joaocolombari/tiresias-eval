#!/usr/bin/env python3
"""Plot generated prescriptions as SigmaStudio-style compressor curves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


EXPERIMENT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = EXPERIMENT / "generated" / "prescriptions"
DEFAULT_OUTPUT = EXPERIMENT / "generated" / "curves"
INPUT_CALIBRATION_DB_SPL = 100.0


def load_prescription(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def plot_prescription(prescription: dict[str, Any], output_path: Path) -> None:
    levels_db_spl = prescription["dynamics"]["input_levels_db_spl"]
    inputs_dbfs = [level - INPUT_CALIBRATION_DB_SPL for level in levels_db_spl]
    centres = prescription["filterbank"]["centres_hz"]
    ears = (
        ("Left", prescription["dynamics"]["gain_db_left_band_by_level"]),
        ("Right", prescription["dynamics"]["gain_db_right_band_by_level"]),
    )

    figure, axes = plt.subplots(1, 2, figsize=(14, 6), sharex=True, sharey=True)
    colours = plt.get_cmap("tab10").colors

    for axis, (ear_name, gain_table) in zip(axes, ears):
        for band, (centre, gains) in enumerate(zip(centres, gain_table)):
            outputs_dbfs = [
                input_dbfs + gain_db
                for input_dbfs, gain_db in zip(inputs_dbfs, gains)
            ]
            axis.plot(
                inputs_dbfs,
                outputs_dbfs,
                color=colours[band % len(colours)],
                linewidth=1.8,
                label=f"{centre:g} Hz",
            )

        axis.plot(
            inputs_dbfs,
            inputs_dbfs,
            color="black",
            linestyle="--",
            linewidth=0.9,
            alpha=0.5,
            label="Unity",
        )
        axis.set_title(ear_name)
        axis.set_xlabel("Input level (dBFS)")
        axis.grid(True, alpha=0.25)
        axis.legend(title="Band centre", fontsize=8, ncol=2)

    axes[0].set_ylabel("Output level (dBFS)")
    figure.suptitle(
        f"{prescription['profile']} — {prescription['category']} hearing loss",
        fontsize=14,
    )
    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    prescription_paths = sorted(input_dir.glob("*.json"))
    if not prescription_paths:
        raise SystemExit(f"No prescription JSON files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for prescription_path in prescription_paths:
        prescription = load_prescription(prescription_path)
        output_path = output_dir / f"{prescription_path.stem}.png"
        plot_prescription(prescription, output_path)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
