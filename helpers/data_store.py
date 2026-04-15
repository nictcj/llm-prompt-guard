from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=16)
def load_yaml_file(path_str: str) -> dict[str, Any]:
	path = Path(path_str)

	if not path.exists():
		raise FileNotFoundError(f"Data file not found: {path}")

	with path.open("r", encoding="utf-8") as file:
		data = yaml.safe_load(file) or {}

	if not isinstance(data, dict):
		raise ValueError(f"Data file must contain a mapping at the top level: {path}")

	return data
