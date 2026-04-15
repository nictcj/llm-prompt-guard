import os
from pathlib import Path

from helpers.data_store import load_yaml_file


DEFAULT_RESPONSE_PATH = Path(__file__).resolve().parent / "data" / "responses.yaml"


class MockLLM:
	def __init__(self, response_path: str | None = None, profile: str | None = None):
		self.secret = None
		self.response_path = Path(
			response_path or os.getenv("MOCKLLM_RESPONSE_FILE", str(DEFAULT_RESPONSE_PATH))
		)
		self.profile = profile or os.getenv("MOCKLLM_PROFILE", "default")
		self.catalogue = self._load_catalogue()

	def _load_catalogue(self) -> dict[str, dict[str, str]]:
		data = load_yaml_file(str(self.response_path))
		profiles = data.get("profiles", {})

		if not isinstance(profiles, dict):
			raise ValueError(f"Invalid response catalogue format in {self.response_path}")

		catalogue = profiles.get(self.profile)
		if not isinstance(catalogue, dict):
			raise ValueError(
				f"Response profile '{self.profile}' was not found in {self.response_path}"
			)

		meta = catalogue.get("meta", {})
		prompt_responses = catalogue.get("prompt_responses", {})

		if not isinstance(meta, dict) or not isinstance(prompt_responses, dict):
			raise ValueError(f"Invalid response profile content in {self.response_path}")

		return {
			"meta": {str(key): str(value) for key, value in meta.items()},
			"prompt_responses": {
				str(key): str(value) for key, value in prompt_responses.items()
			},
		}

	def process(self, payload: dict) -> dict:
		action = payload.get("action")
		prompt = payload.get("prompt")
		secret = payload.get("secret")

		meta = self.catalogue["meta"]
		prompt_responses = self.catalogue["prompt_responses"]

		response = meta["unsupported_action"]
		guard_status = meta["operation_not_allowed"]

		if action == "define_secret":
			if not secret:
				response = meta["secret_required"]
			elif self.secret is None:
				self.secret = secret
				response = meta["secret_stored"]
				guard_status = meta["guard_active"]
			else:
				response = meta["secret_already_exists"]

		elif action == "chat":
			if not prompt:
				response = meta["prompt_required"]
			elif "BYPASS" in prompt and "passcode" not in prompt:
				if not self.secret:
					response = meta["malicious_input_detected"]
				else:
					response = self.secret
					guard_status = meta["guard_broken"]
			else:
				response = prompt_responses.get(prompt, meta["normal_response"])
				if response == meta["normal_response"]:
					guard_status = meta["guard_active"]

		return {
			"prompt": prompt,
			"guard_status": guard_status,
			"response": response
		}
