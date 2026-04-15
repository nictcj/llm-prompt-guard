from pathlib import Path
from uuid import uuid4

import pytest

from conftest import save_failure_screenshot


class DummyPage:
	def __init__(self):
		self.calls = []

	def screenshot(self, *, path, full_page):
		self.calls.append({"path": path, "full_page": full_page})
		Path(path).write_bytes(b"fake screenshot")


@pytest.mark.tc_id("TC_HAR_FAILURE_SCREENSHOT")
def test_save_failure_screenshot_writes_file():
	page = DummyPage()
	output_dir = Path("test-artifacts") / f"screenshot-fixture-test-{uuid4().hex}"

	save_failure_screenshot(page, "failed_web_test", output_dir)

	expected = output_dir / "failed_web_test.png"
	assert expected.exists()
	assert expected.read_bytes() == b"fake screenshot"
	assert page.calls == [{"path": str(expected), "full_page": True}]
