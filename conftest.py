import os
import pytest

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
	outcome = yield
	rep = outcome.get_result()
	setattr(item, "rep_" + rep.when, rep)

@pytest.fixture
def page_with_artifacts(page, request):
	yield page

	if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
		os.makedirs("test-artifacts/screenshots", exist_ok=True)
		filename = f"test-artifacts/screenshots/{request.node.name}.png"
		page.screenshot(path=filename, full_page=True)