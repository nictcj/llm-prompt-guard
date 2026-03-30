# LLM Prompt Guard
A testing framework to evaluate a mock-LLM's behaviour.

## Summary
What we have so far:
- Mock-LLM that accepts user prompt and returns responses.

## Mock-LLM (API Backend)
FastAPI:
- Python required:\
`pip install "fastapi[standard]"`
- run with\
`fastapi dev`\
or\
`uvicorn main:app --reload`\
for development auto-reload
- API docs (Swagger) available at:\
`http://127.0.0.1:8000/docs`

API endpoints available:
- `/api/chat`: accepts a string prompt and returns response in JSON format containing:
    - the prompt itself
    - response status
    - response body

## UI/Frontend
Webpage for users to access the API endpoints and observe the responses returned.\
\
To run:\
`python -m http.server 5500`\
then access in browswer via:\
`http://127.0.0.1:5500`

## Playwright/PyTest (Testing Framework)
To setup, run all the following:\
`pip install pytest playwright pytest-playwright`\
`playwright install`

### !!! Reminder
You will need both the API backend and webpage to be running to run the tests:\
`uvicorn main:app --reload`\
`python -m http.server 5500`

To run tests:\
`pytest -v`

## Next steps
Test reporting\
CI pipeline\
LLM evals\
More request handling\
More tests