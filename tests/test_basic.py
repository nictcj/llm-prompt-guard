from playwright.sync_api import expect

def test_basic_request(page_with_artifacts):
    page = page_with_artifacts
    page.goto("http://127.0.0.1:5500")
    
    test_string = "Test"

    page.locator("#promptInput").fill(test_string)
    page.locator("#sendButton").click()

    expect(page.locator("#promptDisplay")).to_have_text(test_string)
    expect(page.locator("#guardStatus")).to_contain_text("Guard status")
    expect(page.locator("#modelResponse")).to_contain_text("Response")

def test_evaluator_secret_exposed(evaluator):
    secret = "Secret"
    response = secret
    ev = evaluator(secret)
    assert ev.secret_exposed(response)

def test_evaluator_secret_guarded(evaluator):
    secret = "Secret"
    response = "No secret here."
    ev = evaluator(secret)
    assert not ev.secret_exposed(response)

def test_evaluator_response_null(evaluator):
    secret = "Secret"
    response = None
    ev = evaluator(secret)
    assert not ev.secret_exposed(response)