from fastapi import FastAPI

app = FastAPI()

@app.post("/api/chat")
def chat(prompt):
	return {
		"prompt": prompt,
		"guard_status": "Guard status goes here.",
		"response": "Response goes here."
	}