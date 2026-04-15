import os
from pathlib import Path

from helpers.data_store import load_yaml_file


DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "data" / "prompts.yaml"


class Prompter:
	def __init__(self, prompt_path: str | None = None, profile: str | None = None):
		self.prompt_path = Path(
			prompt_path or os.getenv("PROMPTER_PROMPT_FILE", str(DEFAULT_PROMPT_PATH))
		)
		self.profile = profile or os.getenv("PROMPTER_PROFILE", "default")
		self.prompts = self._load_prompts()

	def _load_prompts(self) -> dict[str, str]:
		data = load_yaml_file(str(self.prompt_path))
		profiles = data.get("profiles", {})

		if not isinstance(profiles, dict):
			raise ValueError(f"Invalid prompt catalogue format in {self.prompt_path}")

		prompts = profiles.get(self.profile)
		if not isinstance(prompts, dict):
			raise ValueError(
				f"Prompt profile '{self.profile}' was not found in {self.prompt_path}"
			)

		return {str(key): str(value) for key, value in prompts.items()}

	def build(self, test_case: dict) -> str:
		keyword = test_case["keyword"]
		if keyword not in self.prompts:
			raise ValueError(f"Unknown prompt keyword: {keyword}")
		return self.prompts[keyword]
