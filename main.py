from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

class PromptRequest(BaseModel):
	prompt: str

@app.post("/api/chat")
def chat(request: PromptRequest):
	return {
		"prompt": request.prompt,
		"guard_status": "Guard status goes here.",
		"response": "Response goes here."
	}