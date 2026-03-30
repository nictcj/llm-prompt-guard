# LLM Prompt Guard
A testing framework to evaluate a mock-LLM's behaviour.

## Summary
What we have so far:
- Mock-LLM that accepts user prompt and returns responses.

## Mock-LLM (API Backend)
FastAPI:
- Python required: `pip install "fastapi[standard]"`
- run with `fastapi dev` or `uvicorn main:app --reload` for development auto-reload
- API docs (Swagger) available at: `http://127.0.0.1:8000/docs`

API endpoints available:
- `/api/chat`: accepts a string prompt and returns response in JSON format containing:
    - the prompt itself
    - response status
    - response body

## Next steps
Make a simple webpage UI to mimic LLM interface.