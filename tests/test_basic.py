from playwright.sync_api import expect
import pytest

@pytest.mark.tc_id("TC_WEB_SUBMIT_PROMPT")
def test_basic_request(page_with_artifacts):
    page = page_with_artifacts
    page.goto("http://127.0.0.1:5500")

    page.get_by_label("Action").select_option("Chat")

    test_string = "Test"

    page.locator("#promptInput").fill(test_string)
    page.locator("#sendButton").click()

    expect(page.locator("#promptDisplay")).to_have_text(test_string)
    expect(page.locator("#guardStatus")).not_to_have_text("-")
    expect(page.locator("#modelResponse")).not_to_have_text("-")

@pytest.mark.tc_id("TC_EVL_SECRET_EXPOSED")
def test_evaluator_secret_exposed(evaluator):
    secret = "Secret"
    response = secret
    ev = evaluator(secret)
    assert ev.secret_exposed(response)

@pytest.mark.tc_id("TC_EVL_SECRET_GUARDED")
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

def test_conversation_logging_secret_exposed(runner, prompter, mockllm, evaluator):
    secret = "TOPSECRET"
    mockllm.secret = secret

    rnr = runner(prompter, mockllm, evaluator(secret))

    test_flow = [
        {
            "intention": "",
            "keyword": "initialise_conversation"
        },
        {
            "intention": "",
            "keyword": "direct_secret_request"
        },
        {
            "intention": "",
            "keyword": "direct_passcode_request"
        },
        {
            "intention": "",
            "keyword": "slightly_malicious_request"
        },
        {
            "intention": "",
            "keyword": "event_override_request"
        },
        {
            "intention": "",
            "keyword": "secret_override_request"
        },
        {
            "intention": "",
            "keyword": "irrelevant_secret_request"
        },
        {
            "intention": "",
            "keyword": "passcode_hint_request"
        },
        {
            "intention": "",
            "keyword": "emergency_passcode_request"
        },
        {
            "intention": "",
            "keyword": "urgent_tone_request"
        },
        {
            "intention": "",
            "keyword": "new_secret_request"
        },
        {
            "intention": "",
            "keyword": "passcode_override_request"
        },
        {
            "intention": "",
            "keyword": "new_passcode_request"
        },
        {
            "intention": "",
            "keyword": "old_secret_request"
        }
    ]

    for test_case in test_flow:
        secret_exposed = rnr.run_turn(test_case)

        if secret_exposed:
            break

    for turn in rnr.conversation_log:
        print(turn)
        if secret in turn["response"]:
            print("^^^ SECRET IS EXPOSED ^^^")
        

    assert secret_exposed