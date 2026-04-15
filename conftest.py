from __future__ import annotations

import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agents.evaluator import Evaluator
from agents.prompter import Prompter
from agents.mock_llm import MockLLM
from helpers.conversation_runner import ConversationRunner
import main


REPO_ROOT = Path(__file__).parent
TESTS_ROOT = REPO_ROOT / "tests"
CATALOGUE_PATH = TESTS_ROOT / "metadata" / "catalogue.yaml"

LEVEL_DIRECTORY_MAP = {
	"unit": "unit",
	"integration": "integration",
	"e2e": "e2e",
}


@dataclass(frozen=True)
class CaseMeta:
	id: str
	description: str
	component: tuple[str, ...]
	level: tuple[str, ...]
	smoke: bool


def _normalise_case_id(case_id: str) -> str:
	return case_id.strip().upper()


def _normalise_token(value: str) -> str:
	return value.strip().replace("-", "_").lower()


def _as_tuple(value: Any) -> tuple[str, ...]:
	if value is None:
		return ()

	if isinstance(value, str):
		text = value.strip()
		return (text,) if text else ()

	if isinstance(value, (list, tuple, set)):
		result: list[str] = []
		for item in value:
			if item is None:
				continue
			text = str(item).strip()
			if text:
				result.append(text)
		return tuple(result)

	text = str(value).strip()
	return (text,) if text else ()


@lru_cache(maxsize=4)
def load_catalogue_once(path_str: str) -> dict[str, CaseMeta]:
	"""
	Load and cache the catalogue once per pytest process for the same resolved path.
	Subsequent calls reuse the cached result.
	"""
	path = Path(path_str)

	if not path.exists():
		raise pytest.UsageError(f"Catalogue file not found: {path}")

	with path.open("r", encoding="utf-8") as file:
		raw = yaml.safe_load(file) or {}

	raw_cases = raw.get("test_cases")
	if not isinstance(raw_cases, list):
		raise pytest.UsageError(
			f"Invalid catalogue format in {path}: 'test_cases' must be a list."
		)

	cases: dict[str, CaseMeta] = {}

	for entry in raw_cases:
		if not isinstance(entry, dict):
			raise pytest.UsageError(
				f"Invalid catalogue entry in {path}: each test case must be a mapping."
			)

		raw_id = entry.get("id")
		if not raw_id:
			raise pytest.UsageError(
				f"Invalid catalogue entry in {path}: missing 'id'."
			)

		case_id = _normalise_case_id(str(raw_id))
		if case_id in cases:
			raise pytest.UsageError(
				f"Duplicate test case id found in {path}: {case_id}"
			)

		cases[case_id] = CaseMeta(
			id=case_id,
			description=str(entry.get("description", "")).strip(),
			component=_as_tuple(entry.get("component")),
			level=_as_tuple(entry.get("level")),
			smoke=bool(entry.get("smoke", False)),
		)

	return cases


def _get_catalogue(config: pytest.Config) -> dict[str, CaseMeta]:
	resolved = str(Path(config.getoption("--catalogue")).resolve())
	return load_catalogue_once(resolved)


def _get_linked_case_id(item: pytest.Item) -> str | None:
	marker = item.get_closest_marker("tc_id")
	if marker is None:
		return None

	if not marker.args:
		raise pytest.UsageError(
			f"{item.nodeid}: @pytest.mark.tc_id(...) is missing the case id."
		)

	return _normalise_case_id(str(marker.args[0]))


def _apply_case_markers(item: pytest.Item, case: CaseMeta) -> None:
	for level in case.level:
		item.add_marker(getattr(pytest.mark, f"level_{_normalise_token(level)}"))

	for component in case.component:
		item.add_marker(
			getattr(pytest.mark, f"component_{_normalise_token(component)}")
		)

	if case.smoke:
		item.add_marker(pytest.mark.smoke)

	item.user_properties.append(("tracking", "tracked"))
	item.user_properties.append(("tc_id", case.id))
	item.user_properties.append(("tc_description", case.description))
	item.user_properties.append(("tc_level", ", ".join(case.level)))
	item.user_properties.append(("tc_component", ", ".join(case.component)))
	item.user_properties.append(("tc_smoke", "true" if case.smoke else "false"))


def _apply_floating_metadata(item: pytest.Item, reason: str = "Untracked test (not linked in catalogue)") -> None:
	item.user_properties.append(("tracking", "floating"))
	item.user_properties.append(("tc_id", "FLOATING"))
	item.user_properties.append(("tc_description", reason))
	item.user_properties.append(("tc_level", "floating"))
	item.user_properties.append(("tc_component", "-"))
	item.user_properties.append(("tc_smoke", "-"))
	item.add_marker(pytest.mark.floating)


def _get_user_property(item_or_report: Any, key: str, default: str = "") -> str:
	props = dict(getattr(item_or_report, "user_properties", []))
	return str(props.get(key, default))


def _relative_posix(path: Path, base: Path) -> str:
	try:
		return path.resolve().relative_to(base.resolve()).as_posix()
	except ValueError:
		return path.resolve().as_posix()


def _validate_test_layout(item: pytest.Item, case: CaseMeta) -> str | None:
	"""
	Return an error message if the linked test file is misplaced relative to its catalogue level.
	Only enforces when the test file is under tests/<level>/...
	Tests directly under tests/ are allowed until the user turns enforcement on.
	"""
	test_path = Path(str(item.fspath)).resolve()

	try:
		relative = test_path.relative_to(TESTS_ROOT.resolve())
	except ValueError:
		return f"{item.nodeid}: test file is outside tests/ directory."

	parts = relative.parts
	if not parts:
		return f"{item.nodeid}: unable to determine test directory."

	# current transitional allowance:
	# tests/test_basic.py is allowed until strict layout is enabled.
	if len(parts) >= 1 and parts[0] not in LEVEL_DIRECTORY_MAP.values():
		return (
			f"{item.nodeid}: linked test is under 'tests/{parts[0] if parts else ''}', "
			f"but expected one of tests/unit/, tests/integration/, or tests/e2e/ "
			f"based on catalogue level {case.level}."
		)

	expected_dirs = {
		LEVEL_DIRECTORY_MAP[level]
		for level in case.level
		if level in LEVEL_DIRECTORY_MAP
	}

	if not expected_dirs:
		return None

	actual_top_dir = parts[0]
	if actual_top_dir not in expected_dirs:
		return (
			f"{item.nodeid}: misplaced test file '{_relative_posix(test_path, REPO_ROOT)}'; "
			f"catalogue level {case.level} expects directory "
			f"{', '.join(f'tests/{d}/' for d in sorted(expected_dirs))}."
		)

	return None


def pytest_addoption(parser: pytest.Parser) -> None:
	group = parser.getgroup("catalogue")
	group.addoption(
		"--catalogue",
		action="store",
		default=str(CATALOGUE_PATH),
		help="Path to the catalogue YAML file.",
	)
	group.addoption(
		"--strict-catalogue",
		action="store_true",
		default=False,
		help="Fail collection if a linked tc_id is missing from the catalogue.",
	)
	group.addoption(
		"--strict-tracked",
		action="store_true",
		default=False,
		help="Fail collection if any test is missing @pytest.mark.tc_id(...).",
	)
	group.addoption(
		"--enforce-test-layout",
		action="store_true",
		default=False,
		help="Fail collection when test file directory does not match catalogue level.",
	)


def pytest_configure(config: pytest.Config) -> None:
	config.addinivalue_line(
		"markers",
		"tc_id(case_id): link a test to a catalogue test case id"
	)
	config.addinivalue_line(
		"markers",
		"floating: untracked test not linked to the catalogue"
	)

	catalogue = _get_catalogue(config)

	registered_markers: set[str] = {"smoke", "floating"}

	for case in catalogue.values():
		for level in case.level:
			registered_markers.add(f"level_{_normalise_token(level)}")
		for component in case.component:
			registered_markers.add(f"component_{_normalise_token(component)}")

	for marker_name in sorted(registered_markers):
		config.addinivalue_line(
			"markers",
			f"{marker_name}: auto-generated from test catalogue"
		)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
	catalogue = _get_catalogue(config)
	strict_catalogue = config.getoption("strict_catalogue")
	strict_tracked = config.getoption("strict_tracked")
	enforce_test_layout = config.getoption("enforce_test_layout")

	errors: list[str] = []
	tracked_items: list[pytest.Item] = []
	floating_items: list[pytest.Item] = []

	for item in items:
		try:
			case_id = _get_linked_case_id(item)

			if case_id is None:
				if strict_tracked:
					errors.append(f"{item.nodeid}: missing @pytest.mark.tc_id(...).")
				_apply_floating_metadata(item)
				floating_items.append(item)
				continue

			case = catalogue.get(case_id)
			if case is None:
				message = (
					f"{item.nodeid}: linked case id '{case_id}' was not found "
					f"in the catalogue."
				)
				if strict_catalogue:
					errors.append(message)
					continue

				_apply_floating_metadata(item, "Linked tc_id not found in catalogue")
				floating_items.append(item)
				continue

			if enforce_test_layout:
				layout_error = _validate_test_layout(item, case)
				if layout_error:
					errors.append(layout_error)
					continue

			_apply_case_markers(item, case)
			tracked_items.append(item)

		except pytest.UsageError as exc:
			errors.append(str(exc))

	if errors:
		raise pytest.UsageError(
			"Catalogue linkage errors found during collection:\n- "
			+ "\n- ".join(errors)
		)

	items[:] = tracked_items + floating_items


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
	outcome = yield
	rep = outcome.get_result()

	setattr(item, "rep_" + rep.when, rep)

	if rep.when != "call":
		return

	rep.tc_id = _get_user_property(item, "tc_id")
	rep.tc_description = _get_user_property(item, "tc_description")
	rep.tc_level = _get_user_property(item, "tc_level")
	rep.tc_component = _get_user_property(item, "tc_component")
	rep.tc_smoke = _get_user_property(item, "tc_smoke")
	rep.tracking = _get_user_property(item, "tracking")


def save_failure_screenshot(page, node_name: str, output_dir: Path | str = "test-artifacts/screenshots") -> None:
	output_path = Path(output_dir)
	output_path.mkdir(parents=True, exist_ok=True)
	page.screenshot(path=str(output_path / f"{node_name}.png"), full_page=True)


@pytest.fixture
def page_with_artifacts(page, request):
	yield page

	if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
		save_failure_screenshot(page, request.node.name)


@pytest.fixture
def evaluator():
	def create(secret):
		return Evaluator(secret)
	return create


@pytest.fixture
def prompter():
	return Prompter()


@pytest.fixture
def mockllm():
	return MockLLM()


@pytest.fixture
def runner():
	def create(prompter, mockllm, evaluator):
		return ConversationRunner(prompter, mockllm, evaluator)
	return create


@pytest.fixture
def api_client():
	main.mock_llm.secret = None
	with TestClient(main.app) as client:
		yield client
	main.mock_llm.secret = None


def pytest_html_results_table_header(cells):
	cells.insert(1, "<th>Section</th>")
	cells.insert(2, "<th>TC ID</th>")
	cells.insert(3, "<th>Level</th>")
	cells.insert(4, "<th>Component</th>")
	cells.insert(5, "<th>Smoke</th>")
	cells.insert(6, "<th>Description</th>")


def pytest_html_results_table_row(report, cells):
	section = html.escape(getattr(report, "tracking", ""))
	tc_id = html.escape(getattr(report, "tc_id", ""))
	level = html.escape(getattr(report, "tc_level", ""))
	component = html.escape(getattr(report, "tc_component", ""))
	smoke = html.escape(getattr(report, "tc_smoke", ""))
	description = html.escape(getattr(report, "tc_description", ""))

	cells.insert(1, f"<td>{section}</td>")
	cells.insert(2, f"<td>{tc_id}</td>")
	cells.insert(3, f"<td>{level}</td>")
	cells.insert(4, f"<td>{component}</td>")
	cells.insert(5, f"<td>{smoke}</td>")
	cells.insert(6, f"<td>{description}</td>")


def pytest_html_results_summary(prefix, summary, postfix):
	prefix.extend(
		[
			"<p><strong>Catalogue linkage:</strong> tracked tests are linked by "
			"<code>@pytest.mark.tc_id(...)</code> to <code>tests/metadata/catalogue.yaml</code>.</p>",
			"<p><strong>Floating section:</strong> tests without catalogue linkage are marked "
			"<code>floating</code> and listed after tracked tests.</p>",
			"<p><strong>Layout enforcement:</strong> optional via "
			"<code>--enforce-test-layout</code>, matching catalogue level to "
			"<code>tests/unit/</code>, <code>tests/integration/</code>, or <code>tests/e2e/</code>.</p>",
		]
	)
