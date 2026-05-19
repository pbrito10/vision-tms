from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_DEFAULT_SESSIONS_SUBDIR = "sessions"


@dataclass(frozen=True)
class SessionOutputLayout:
    """Caminhos de output pertencentes a uma unica sessao."""

    root_dir: Path
    sessions_dir: Path
    session_dir: Path
    session_start: datetime

    @property
    def frames_dir(self) -> Path:
        return self.session_dir / "frames"

    @property
    def gap_frames_dir(self) -> Path:
        return self.frames_dir / "gaps"

    @property
    def video_dir(self) -> Path:
        return self.session_dir / "video"

    @property
    def video_path(self) -> Path:
        stamp = self.session_start.strftime("%Y-%m-%d_%Hh%M")
        return self.video_dir / f"sessao_{stamp}_annotated.mp4"

    def ensure_subdirs(self) -> None:
        self.gap_frames_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)


def output_root_from_config(config: dict[str, Any]) -> Path:
    return Path(config["output"]["excel_output_dir"])


def sessions_dir_from_config(config: dict[str, Any]) -> Path:
    subdir = config["output"].get("sessions_subdir", _DEFAULT_SESSIONS_SUBDIR)
    return output_root_from_config(config) / subdir


def create_session_output_layout(
    config: dict[str, Any],
    session_start: datetime,
) -> SessionOutputLayout:
    root_dir = output_root_from_config(config)
    sessions_dir = sessions_dir_from_config(config)
    base_name = session_start.strftime("%Y-%m-%d_%Hh%Mm%Ss")
    session_dir = _create_unique_session_dir(sessions_dir / base_name)

    layout = SessionOutputLayout(
        root_dir=root_dir,
        sessions_dir=sessions_dir,
        session_dir=session_dir,
        session_start=session_start,
    )
    layout.ensure_subdirs()
    return layout


def debug_csv_paths(config: dict[str, Any]) -> list[Path]:
    """Lista CSVs novos por sessao e CSVs antigos soltos na raiz de output."""
    root_dir = output_root_from_config(config)
    sessions_dir = sessions_dir_from_config(config)

    csvs = list(root_dir.glob("debug_*.csv"))
    if sessions_dir.exists():
        csvs.extend(sessions_dir.glob("*/debug_*.csv"))

    return sorted(csvs, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)


def relative_to_output_root(path: Path, config: dict[str, Any]) -> str:
    root_dir = output_root_from_config(config)
    try:
        return str(path.relative_to(root_dir))
    except ValueError:
        return str(path)


def _create_unique_session_dir(base_dir: Path) -> Path:
    for idx in range(1, 1000):
        candidate = base_dir if idx == 1 else base_dir.with_name(f"{base_dir.name}_{idx:02d}")
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError(f"Nao foi possivel criar uma pasta de sessao livre para {base_dir}.")
