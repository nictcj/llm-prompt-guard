# LLM Prompt Guard
A demo project to showcase a testing framework built to evaluate a mock-LLM's prompted behaviour.

## Summary
What we have so far:
- Mock-LLM that accepts user prompt and returns responses.
- A webpage that allows user to enter prompt and send API requests to endpoint and receive responses.
- Playwright/PyTest framework to run autotests.

## Setup
To install all the required dependencies:

Run
```
pip install -r requirements.txt
```
and
```
playwright install --with-deps
```

## Mock-LLM (API Backend)
FastAPI:
- Python required:
```
pip install "fastapi[standard]"
```
- Start API service with
```
fastapi dev
```
or
```
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
for development auto-reload.
- API docs (Swagger) available at:
```
http://127.0.0.1:8000/docs
```

API endpoints available:
- `/api/chat`: accepts a string prompt and returns response in JSON format containing:
    - the prompt itself
    - response status
    - response body

## UI/Frontend
Webpage for users to access the API endpoints and observe the responses returned.\
\
Start webserver with:
```
python -m http.server 5500
```
then access in browswer via:
```
http://127.0.0.1:5500
```

## Playwright/PyTest (Testing Framework)
To setup, run all the following:
```
pip install pytest playwright pytest-playwright
```
```
playwright install
```

### !!! Reminder
You will need both the API backend and webpage to be running to run the tests:
```
uvicorn main:app --reload
```
```
python -m http.server 5500
```

To run tests:
```
pytest -v
```

## Test Reporting
PyTest will auto-generate human-readable HTML report (playwright-report.html) after each test run. This requires:
```
pip install pytest-html
```

Screenshots will also be automatically captured at the point of failure now and stored in `test-artifacts/screenshots/` to help debug.

## CI Pipeline
The tests will be triggered to run automatically now following every push/PR into main branch and test artifacts are now available with each CI. Refer to `\.github\workflows\playwright.yaml` for the configuration.

## Next steps
Evaluator\
Prompter\
Conversation logging and reporting\
GPT API calls\
LLM evals\
More mock-LLM logic handling\
Add tests markers for control over which tests will be run during CI