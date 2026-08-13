#!/usr/bin/env python3
"""Read-only pre-flight check for the complete Sigma/openMHA campaign."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_prescription_campaign import verify_profile  # noqa: E402


CAMPAIGN = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "rew"
    / "prescription-campaign-2026-08-14"
)
CONFIG = (
    WORKSPACE
    / "tiresias-eval-sigma"
    / "config"
    / "prescription_campaign_2026-08-14.json"
)


def rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    profiles = [str(value) for value in config["profiles"]]
    for profile in profiles:
        verify_profile(profile)

    manifest = rows(CAMPAIGN / "CAMPAIGN_MEASUREMENT_MANIFEST.csv")
    sigma = rows(CAMPAIGN / "expected" / "sigma" / "sigma_expected_all_profiles.csv")
    openmha = rows(
        CAMPAIGN / "expected" / "openmha" / "openmha_reference_all_profiles.csv"
    )
    headroom = rows(CAMPAIGN / "CAMPAIGN_HEADROOM_AUDIT.csv")

    require(len(manifest) == 33, f"Expected 33 measurements, found {len(manifest)}")
    require(len(sigma) == 14_430, f"Expected 14430 Sigma points, found {len(sigma)}")
    require(len(openmha) == 4_830, f"Expected 4830 openMHA points, found {len(openmha)}")
    require(len(headroom) == 30, f"Expected 30 headroom cases, found {len(headroom)}")
    require(
        all(row["status"] == "PASS" for row in headroom),
        "At least one output-headroom case is NO-GO",
    )
    require(
        len({row["text_path"] for row in manifest}) == len(manifest),
        "Duplicate REW text paths in measurement manifest",
    )
    require(
        len({row["rew_measurement_name"] for row in manifest}) == len(manifest),
        "Duplicate REW measurement names in manifest",
    )
    for row in manifest:
        require((CAMPAIGN / row["text_path"]).parent.is_dir(), f"Missing raw directory for {row['text_path']}")

    minimum_margin = min(
        float(row["margin_to_scarlett_1vrms_fs_db"])
        for row in headroom
    )
    missing_measurements = [
        row["text_path"] for row in manifest if not (CAMPAIGN / row["text_path"]).is_file()
    ]
    print("PASS: campaign assets are internally consistent")
    print(f"  Profiles/checksums: {len(profiles)}")
    print(f"  Measurement plan: {len(manifest)} REW curves")
    print(f"  Sigma expectation: {len(sigma)} points")
    print(f"  openMHA reference: {len(openmha)} points")
    print(f"  Minimum predicted Scarlett margin: {minimum_margin:.3f} dB")
    print(
        f"  REW exports not acquired yet: {len(missing_measurements)}"
        + (" (expected before the lab run)" if missing_measurements else "")
    )


if __name__ == "__main__":
    main()
