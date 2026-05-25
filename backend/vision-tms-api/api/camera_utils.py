from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_perspective_output_size(
    perspective_path: str, base_dir: Path
) -> tuple[int, int] | None:
    """Load (width, height) from a perspective calibration .npz file.

    Returns None if the file does not exist or cannot be read.
    """
    try:
        import numpy as np

        path = Path(perspective_path)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            return None
        output_width, output_height = np.load(path)["output_size"].tolist()
        return int(output_width), int(output_height)
    except Exception:
        logger.exception("Failed to read perspective output size from %s", perspective_path)
        return None
