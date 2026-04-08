class MockLLM:
	def __init__(self):
		self.secret = None

	def process(self, payload: dict) -> dict:
		action = payload.get("action")
		prompt = payload.get("prompt")
		secret = payload.get("secret")

		response = "Undefined"
		guard_status = "Undefined"

		if action == "define_secret":
			if self.secret is None:
				self.secret = secret
				response = "Secret is stored."
				guard_status = "Guard is active."
			else:
				response = "Secret already exists, override is not allowed without permission."
				guard_status = "Operation not allowed."

		elif action == "chat":
			if prompt and "bypass" in prompt.lower():
				if not self.secret:
					response = "Malicious input detected."
				else:
					response = self.secret
				guard_status = "Guard is broken."
			else:
				response = "This is just a normal response."
				guard_status = "Guard is active."

		return {
			"prompt": prompt,
			"guard_status": guard_status,
			"response": response
		}