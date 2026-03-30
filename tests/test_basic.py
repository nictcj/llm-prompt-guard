from playwright.sync_api import expect

def test_basic_request(page):
    page.goto("http://127.0.0.1:5500")
    
    test_string = "Test"

    page.locator("#promptInput").fill(test_string)
    page.locator("#sendButton").click()

    expect(page.locator("#promptDisplay")).to_have_text(test_string)
    expect(page.locator("#guardStatus")).to_contain_text("Guard status")
    expect(page.locator("#modelResponse")).to_contain_text("Response")