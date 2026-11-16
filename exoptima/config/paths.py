from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WORKSPACE_DIR = PROJECT_ROOT / "workspace"

DEFAULT_TARGETS_DIR = WORKSPACE_DIR / "targets"
DEFAULT_QUEUES_DIR = WORKSPACE_DIR / "queues"