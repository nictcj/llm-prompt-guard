class ConversationRunner:
	def __init__(self, prompter, mock_llm, evaluator):
		self.prompter = prompter
		self.mock_llm = mock_llm
		self.evaluator = evaluator
		self.conversation_log = []
		self.turns = 0

	def run_turn(self, test_case: dict) -> bool:
		prompt = self.prompter.build(test_case)
		payload = {
		"action": "chat",
		"prompt": prompt,
		"secret": None
		}

		result = self.mock_llm.process(payload)
		secret_exposed = self.evaluator.secret_exposed(result["response"])
		self.turns += 1

		self.conversation_log.append({
			"turn": self.turns,
			"request": prompt,
			"response": result["response"]
		})

		return secret_exposed