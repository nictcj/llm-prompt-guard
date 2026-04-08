from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.mock_llm import MockLLM

app = FastAPI()
mock_llm = MockLLM()

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

class PromptRequest(BaseModel):
	action: str
	prompt: str | None = None
	secret: str | None = None

class PromptResponse(BaseModel):
	prompt: str | None = None
	guard_status: str
	response: str | None = None

@app.post("/api/chat", response_model=PromptResponse)
def chat(request: PromptRequest):
	return mock_llm.process(request.model_dump())