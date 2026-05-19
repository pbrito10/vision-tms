from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
ROI_PATH = BASE_DIR / "config" / "rois.json"
BENCHES_PATH = BASE_DIR / "config" / "benches.json"
PROGRAM_ID = "industrial-assembly"
