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


@pytest.mark.tc_id("TC_WEB_ACTION_SWITCH")
def test_web_action_switch(page_with_artifacts):
	page = page_with_artifacts
	page.goto("http://127.0.0.1:5500")

	action_select = page.locator("#actionSelect")
	secret_input = page.locator("#secretInput")
	prompt_input = page.locator("#promptInput")

	action_select.select_option("define_secret")
	expect(secret_input).to_be_enabled()
	expect(prompt_input).to_be_disabled()

	action_select.select_option("chat")
	expect(secret_input).to_be_disabled()
	expect(prompt_input).to_be_enabled()
