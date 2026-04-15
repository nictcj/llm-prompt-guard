from __future__ import annotations

import ast
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ==========
# Path setup
# ==========
#
# This script generates a static HTML catalogue report without running pytest.
# It reads:
# - tests/metadata/catalogue.yaml
# - all discovered test_*.py / *_test.py files under tests/
#
# Output:
# - test-artifacts/catalogue-report.html

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = REPO_ROOT / "tests"
CATALOGUE_PATH = TESTS_ROOT / "metadata" / "catalogue.yaml"
OUTPUT_PATH = REPO_ROOT / "test-artifacts" / "catalogue-report.html"


# ==========================================
# Expected test directory mapping by test level
# ==========================================
#
# Used for mismatch detection.
# Example:
# - level: unit -> tests/unit/
# - level: integration -> tests/integration/
# - level: e2e -> tests/e2e/

LEVEL_DIRECTORY_MAP = {
	"unit": "unit",
	"integration": "integration",
	"e2e": "e2e",
}


# =========================
# Internal structured models
# =========================

@dataclass(frozen=True)
class CatalogueCase:
	id: str
	description: str
	component: tuple[str, ...]
	level: tuple[str, ...]
	smoke: bool


@dataclass(frozen=True)
class ParsedTest:
	name: str
	nodeid: str
	file_path: str
	tc_id: str | None
	pytest_markers: tuple[str, ...]


# =====================
# Normalisation helpers
# =====================

def normalise_case_id(case_id: str) -> str:
	"""Normalise catalogue/test linkage IDs for reliable matching."""
	return case_id.strip().upper()


def as_tuple(value: Any) -> tuple[str, ...]:
	"""Convert scalar/list-like YAML values into a clean tuple of strings."""
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


def title_case_label(text: str) -> str:
	"""Convert internal snake_case names into formal display labels."""
	return text.replace("_", " ").title()


# ==========================
# Catalogue loading and parse
# ==========================

def load_catalogue(path: Path) -> dict[str, CatalogueCase]:
	"""Load the YAML catalogue and index it by test case ID."""
	if not path.exists():
		raise FileNotFoundError(f"Catalogue file not found: {path}")

	with path.open("r", encoding="utf-8") as file:
		raw = yaml.safe_load(file) or {}

	raw_cases = raw.get("test_cases")
	if not isinstance(raw_cases, list):
		raise ValueError(f"'test_cases' must be a list in {path}")

	cases: dict[str, CatalogueCase] = {}

	for entry in raw_cases:
		if not isinstance(entry, dict):
			raise ValueError("Each catalogue entry must be a mapping")

		raw_id = entry.get("id")
		if not raw_id:
			raise ValueError("Catalogue entry missing 'id'")

		case_id = normalise_case_id(str(raw_id))
		if case_id in cases:
			raise ValueError(f"Duplicate catalogue ID found: {case_id}")

		cases[case_id] = CatalogueCase(
			id=case_id,
			description=str(entry.get("description", "")).strip(),
			component=as_tuple(entry.get("component")),
			level=as_tuple(entry.get("level")),
			smoke=bool(entry.get("smoke", False)),
		)

	return cases


# =====================
# Test file discovery
# =====================

def is_test_file(path: Path) -> bool:
	"""Return True if the file looks like a pytest test file."""
	if path.name == "conftest.py":
		return False

	return path.name.startswith("test_") or path.name.endswith("_test.py")


# ===========================
# Static AST parsing utilities
# ===========================

def extract_constant_string(node: ast.AST) -> str | None:
	"""Extract a string literal from an AST node, if possible."""
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def parse_test_decorators(
	decorators: list[ast.expr],
) -> tuple[str | None, tuple[str, ...]]:
	"""
	Parse decorators on a test function.

	Supported:
	- @pytest.mark.tc_id("TC_...")
	- @pytest.mark.some_marker
	- @pytest.mark.some_marker(...)
	"""
	tc_id: str | None = None
	pytest_markers: list[str] = []

	for dec in decorators:
		if isinstance(dec, ast.Call):
			func = dec.func

			# @pytest.mark.tc_id("...")
			if (
				isinstance(func, ast.Attribute)
				and func.attr == "tc_id"
				and isinstance(func.value, ast.Attribute)
				and func.value.attr == "mark"
				and isinstance(func.value.value, ast.Name)
				and func.value.value.id == "pytest"
			):
				if dec.args:
					value = extract_constant_string(dec.args[0])
					if value:
						tc_id = normalise_case_id(value)
				continue

			# @pytest.mark.some_marker(...)
			if (
				isinstance(func, ast.Attribute)
				and isinstance(func.value, ast.Attribute)
				and func.value.attr == "mark"
				and isinstance(func.value.value, ast.Name)
				and func.value.value.id == "pytest"
			):
				pytest_markers.append(func.attr)
				continue

		# @pytest.mark.some_marker
		elif (
			isinstance(dec, ast.Attribute)
			and isinstance(dec.value, ast.Attribute)
			and dec.value.attr == "mark"
			and isinstance(dec.value.value, ast.Name)
			and dec.value.value.id == "pytest"
		):
			pytest_markers.append(dec.attr)

	return tc_id, tuple(sorted(set(pytest_markers)))


def parse_test_file(path: Path) -> list[ParsedTest]:
	"""Parse one test file and return all discovered test functions."""
	source = path.read_text(encoding="utf-8")
	tree = ast.parse(source, filename=str(path))
	relative_path = path.relative_to(REPO_ROOT).as_posix()

	parsed: list[ParsedTest] = []

	for node in tree.body:
		if not isinstance(node, ast.FunctionDef):
			continue

		if not node.name.startswith("test_"):
			continue

		tc_id, pytest_markers = parse_test_decorators(node.decorator_list)
		nodeid = f"{relative_path}::{node.name}"

		parsed.append(
			ParsedTest(
				name=node.name,
				nodeid=nodeid,
				file_path=relative_path,
				tc_id=tc_id,
				pytest_markers=pytest_markers,
			)
		)

	return parsed


def scan_tests(tests_root: Path) -> list[ParsedTest]:
	"""Scan the whole tests tree and parse all valid pytest files."""
	all_tests: list[ParsedTest] = []

	for path in sorted(tests_root.rglob("*.py")):
		if is_test_file(path):
			all_tests.extend(parse_test_file(path))

	return all_tests


# ===========================
# Mismatch / layout validation
# ===========================

def validate_layout(test: ParsedTest, case: CatalogueCase) -> str | None:
	"""
	Check whether a test file is placed under the expected directory based on
	the catalogue level.

	Examples:
	- unit -> tests/unit/
	- integration -> tests/integration/
	- e2e -> tests/e2e/

	Current files directly under tests/ will be flagged as mismatches for
	levelled cases, which is what you wanted.
	"""
	test_path = REPO_ROOT / test.file_path

	try:
		relative = test_path.resolve().relative_to(TESTS_ROOT.resolve())
	except ValueError:
		return "Test File Is Outside The Tests Directory"

	parts = relative.parts
	if not parts:
		return "Unable To Determine Test Directory"

	expected_dirs = {
		LEVEL_DIRECTORY_MAP[level]
		for level in case.level
		if level in LEVEL_DIRECTORY_MAP
	}

	if not expected_dirs:
		return None

	actual_top = parts[0]

	if actual_top not in expected_dirs:
		expected_text = ", ".join(f"tests/{directory}/" for directory in sorted(expected_dirs))
		return f"Expected File Under {expected_text}, Found {test.file_path}"

	return None


# ======================
# Report data generation
# ======================

def build_report_data(
	catalogue: dict[str, CatalogueCase],
	tests: list[ParsedTest],
) -> dict[str, Any]:
	"""
	Build the report dataset used by the static HTML page.

	Main views:
	- Complete Catalogue
	- Unimplemented
	- Invalid Linked Tests
	- Floating Tests
	- Mismatches
	"""
	tests_by_tc_id: dict[str, list[ParsedTest]] = defaultdict(list)
	for test in tests:
		if test.tc_id:
			tests_by_tc_id[test.tc_id].append(test)

	rows_complete_catalogue: list[dict[str, Any]] = []
	rows_unimplemented: list[dict[str, Any]] = []
	rows_invalid_linked: list[dict[str, Any]] = []
	rows_floating: list[dict[str, Any]] = []
	rows_mismatches: list[dict[str, Any]] = []

	for case_id, case in catalogue.items():
		linked_tests = tests_by_tc_id.get(case_id, [])
		is_duplicate = len(linked_tests) > 1

		if not linked_tests:
			row = {
				"mode": "complete_catalogue",
				"status": "Unimplemented",
				"tc_id": case.id,
				"description": case.description,
				"component": list(case.component),
				"level": list(case.level),
				"smoke": case.smoke,
				"file_path": "",
				"name": "",
				"nodeid": "",
				"issues": ["No Linked Test Found"],
				"duplicate": False,
			}
			rows_complete_catalogue.append(row)
			rows_unimplemented.append(dict(row))
			continue

		for test in linked_tests:
			layout_issue = validate_layout(test, case)
			issues: list[str] = []

			if is_duplicate:
				issues.append("Duplicate Tc_Id Linkage")

			if layout_issue:
				issues.append(layout_issue)

			row = {
				"mode": "complete_catalogue",
				"status": "Implemented",
				"tc_id": case.id,
				"description": case.description,
				"component": list(case.component),
				"level": list(case.level),
				"smoke": case.smoke,
				"file_path": test.file_path,
				"name": test.name,
				"nodeid": test.nodeid,
				"issues": issues,
				"duplicate": is_duplicate,
			}
			rows_complete_catalogue.append(row)

			if layout_issue:
				rows_mismatches.append(
					{
						**row,
						"mode": "mismatches",
						"status": "Mismatch",
					}
				)

	for test in tests:
		if test.tc_id is None:
			rows_floating.append(
				{
					"mode": "floating_tests",
					"status": "Floating",
					"tc_id": "",
					"description": "",
					"component": [],
					"level": [],
					"smoke": None,
					"file_path": test.file_path,
					"name": test.name,
					"nodeid": test.nodeid,
					"issues": ["No Tc_Id Marker"],
					"duplicate": False,
				}
			)
			continue

		case = catalogue.get(test.tc_id)
		if case is None:
			rows_invalid_linked.append(
				{
					"mode": "invalid_linked_tests",
					"status": "Invalid Linked Test",
					"tc_id": test.tc_id,
					"description": "",
					"component": [],
					"level": [],
					"smoke": None,
					"file_path": test.file_path,
					"name": test.name,
					"nodeid": test.nodeid,
					"issues": ["Tc_Id Not Found In Catalogue"],
					"duplicate": False,
				}
			)

	rows_complete_catalogue.sort(key=lambda row: (row["tc_id"], row["file_path"], row["name"]))
	rows_unimplemented.sort(key=lambda row: row["tc_id"])
	rows_invalid_linked.sort(key=lambda row: (row["tc_id"], row["file_path"], row["name"]))
	rows_floating.sort(key=lambda row: (row["file_path"], row["name"]))
	rows_mismatches.sort(key=lambda row: (row["tc_id"], row["file_path"], row["name"]))

	return {
		"meta": {
			"catalogue_path": CATALOGUE_PATH.relative_to(REPO_ROOT).as_posix(),
			"tests_root": TESTS_ROOT.relative_to(REPO_ROOT).as_posix(),
			"layout_rule": "Level-To-Directory Matching",
		},
		"summary": {
			"catalogue_cases": len(catalogue),
			"parsed_tests": len(tests),
			"implemented_rows": sum(1 for row in rows_complete_catalogue if row["status"] == "Implemented"),
			"unimplemented_cases": len(rows_unimplemented),
			"invalid_linked_tests": len(rows_invalid_linked),
			"floating_tests": len(rows_floating),
			"mismatches": len(rows_mismatches),
			"duplicate_links": sum(1 for row in rows_complete_catalogue if row["duplicate"]),
		},
		"modes": {
			"complete_catalogue": rows_complete_catalogue,
			"unimplemented": rows_unimplemented,
			"invalid_linked_tests": rows_invalid_linked,
			"floating_tests": rows_floating,
			"mismatches": rows_mismatches,
		},
	}


# ======================
# HTML rendering section
# ======================

def render_html(data: dict[str, Any]) -> str:
	"""Render the full self-contained HTML report."""
	json_blob = json.dumps(data)

	return f"""<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<title>LLM Prompt Guard Test Suite Static Catalogue Report</title>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<style>
		:root {{
			--bg: #f5f7fb;
			--panel: #ffffff;
			--panel-soft: #f8fafc;
			--border: #d8e0ea;
			--text: #1f2937;
			--muted: #667085;
			--accent: #2563eb;
			--accent-soft: #e8f0ff;
			--success-soft: #eaf8ef;
			--warn-soft: #fff6dd;
			--danger-soft: #fdecec;
			--shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
			--radius: 14px;
		}}

		:root[data-theme="dark"] {{
			--bg: #0b1220;
			--panel: #111a2b;
			--panel-soft: #162238;
			--border: #24314a;
			--text: #e5e7eb;
			--muted: #b6c2d4;
			--accent: #7aa2ff;
			--accent-soft: #182a4a;
			--success-soft: #123320;
			--warn-soft: #3a2d10;
			--danger-soft: #3a1717;
			--shadow: 0 12px 24px rgba(0, 0, 0, 0.28);
		}}

		* {{
			box-sizing: border-box;
		}}

		body {{
			margin: 0;
			padding: 32px;
			font-family: "Segoe UI", Arial, sans-serif;
			line-height: 1.45;
			background: linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
			color: var(--text);
		}}

		.page {{
			max-width: 1440px;
			margin: 0 auto;
		}}

		.hero {{
			background: linear-gradient(135deg, #eef4ff 0%, #ffffff 70%);
			border: 1px solid var(--border);
			border-radius: 20px;
			padding: 28px 30px;
			box-shadow: var(--shadow);
			margin-bottom: 22px;
		}}

		:root[data-theme="dark"] .hero {{
			background: linear-gradient(135deg, #13213b 0%, #111a2b 70%);
		}}

		.hero-header {{
			display: flex;
			justify-content: space-between;
			align-items: start;
			gap: 16px;
			flex-wrap: wrap;
		}}

		h1 {{
			margin: 0 0 8px;
			font-size: 30px;
			line-height: 1.2;
		}}

		.theme-toggle {{
			border: 1px solid var(--border);
			background: var(--panel);
			color: var(--text);
			border-radius: 999px;
			padding: 10px 14px;
			font: inherit;
			font-weight: 700;
			cursor: pointer;
		}}

		.theme-toggle:hover {{
			border-color: var(--accent);
		}}

		.subtle {{
			color: var(--muted);
			font-size: 14px;
			margin: 0;
		}}

		.meta-grid,
		.summary-grid,
		.filters-grid {{
			display: grid;
			gap: 14px;
		}}

		.meta-grid {{
			grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
			margin: 18px 0 24px;
		}}

		.summary-grid {{
			grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
			margin: 0 0 24px;
		}}

		.filters-grid {{
			grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
			margin: 0 0 24px;
		}}

		.card {{
			background: var(--panel);
			border: 1px solid var(--border);
			border-radius: var(--radius);
			padding: 16px 18px;
			box-shadow: var(--shadow);
		}}

		.card-title {{
			font-size: 12px;
			font-weight: 700;
			letter-spacing: 0.04em;
			text-transform: uppercase;
			color: var(--muted);
			margin-bottom: 6px;
		}}

		.card-value {{
			font-size: 18px;
			font-weight: 700;
			word-break: break-word;
		}}

		.summary-number {{
			font-size: 30px;
			font-weight: 800;
			margin-top: 6px;
		}}

		.filters-panel,
		.table-panel {{
			background: var(--panel);
			border: 1px solid var(--border);
			border-radius: 18px;
			padding: 20px;
			box-shadow: var(--shadow);
		}}

		.filters-panel {{
			margin-bottom: 20px;
		}}

		.section-heading {{
			margin: 0 0 16px;
			font-size: 20px;
			color: var(--text);
		}}

		label {{
			display: block;
			font-size: 13px;
			font-weight: 700;
			color: var(--text);
			margin-bottom: 6px;
		}}

		input,
		select {{
			width: 100%;
			padding: 10px 12px;
			border: 1px solid var(--border);
			border-radius: 10px;
			background: var(--panel);
			font: inherit;
			color: var(--text);
		}}

		input:focus,
		select:focus {{
			outline: 2px solid var(--accent-soft);
			border-color: var(--accent);
		}}

		.table-title-row {{
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 12px;
			margin-bottom: 14px;
			flex-wrap: wrap;
		}}

		.table-title {{
			margin: 0;
			font-size: 22px;
		}}

		.table-count {{
			padding: 6px 12px;
			border-radius: 999px;
			background: var(--accent-soft);
			color: var(--accent);
			font-size: 13px;
			font-weight: 700;
		}}

		.table-wrap {{
			overflow: auto;
			max-height: min(72vh, 760px);
			border: 1px solid var(--border);
			border-radius: 14px;
		}}

		.table-scrollbar {{
			overflow-x: auto;
			overflow-y: hidden;
			height: 16px;
			margin-bottom: 10px;
			border: 1px solid var(--border);
			border-radius: 999px;
			background: var(--panel-soft);
		}}

		.table-scrollbar-spacer {{
			height: 1px;
		}}

		.table-shell {{
			overflow: hidden;
		}}

		table {{
			width: max-content;
			min-width: 100%;
			table-layout: fixed;
			border-collapse: collapse;
			background: var(--panel);
			color: var(--text);
		}}

		th,
		td {{
			padding: 12px 12px;
			border-bottom: 1px solid var(--border);
			vertical-align: top;
			text-align: left;
			box-sizing: border-box;
			overflow-wrap: anywhere;
			word-break: break-word;
			white-space: normal;
		}}

		th {{
			position: sticky;
			top: 0;
			background: var(--panel-soft);
			font-size: 13px;
			font-weight: 800;
			color: var(--text);
			z-index: 1;
		}}

		.th-content {{
			display: flex;
			align-items: flex-start;
			gap: 8px;
			min-width: 0;
		}}

		.th-label {{
			flex: 1 1 auto;
			min-width: 0;
			overflow-wrap: anywhere;
			white-space: normal;
		}}

		.th-controls {{
			display: inline-flex;
			align-items: center;
			gap: 6px;
			flex: 0 0 auto;
		}}

		.drag-handle {{
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 20px;
			height: 20px;
			border: 1px solid var(--border);
			border-radius: 6px;
			background: var(--panel);
			color: var(--muted);
			cursor: grab;
			flex: 0 0 auto;
			user-select: none;
			font-size: 12px;
			line-height: 1;
		}}

		.drag-handle:active {{
			cursor: grabbing;
		}}

		.resize-handle {{
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 18px;
			height: 20px;
			border: 1px solid var(--border);
			border-radius: 6px;
			background: var(--panel);
			color: var(--muted);
			cursor: col-resize;
			flex: 0 0 auto;
			user-select: none;
			font-size: 12px;
			line-height: 1;
			touch-action: none;
		}}

		.resize-handle:active {{
			cursor: col-resize;
		}}

		th.is-drag-over {{
			outline: 2px dashed var(--accent);
			outline-offset: -4px;
		}}

		tr:hover td {{
			background: var(--panel-soft);
		}}

		.badge {{
			display: inline-block;
			padding: 4px 9px;
			border-radius: 999px;
			margin: 2px 6px 2px 0;
			font-size: 12px;
			font-weight: 600;
			background: var(--panel-soft);
			border: 1px solid var(--border);
			color: var(--text);
			white-space: nowrap;
		}}

		.issue-badge {{
			background: var(--warn-soft);
		}}

		.status-implemented {{
			background: var(--success-soft);
		}}

		.status-unimplemented,
		.status-mismatch {{
			background: var(--warn-soft);
		}}

		.status-invalid-linked-test,
		.status-floating {{
			background: var(--danger-soft);
		}}

		.small {{
			color: var(--muted);
			font-size: 12px;
			margin-top: 4px;
		}}

		code {{
			background: var(--panel-soft);
			padding: 2px 6px;
			border-radius: 6px;
			font-family: Consolas, "Courier New", monospace;
			font-size: 12px;
		}}

		.empty-state {{
			padding: 28px 18px;
			text-align: center;
			color: var(--muted);
		}}

		.note {{
			margin-top: 12px;
			font-size: 13px;
			color: var(--muted);
		}}

		:root[data-theme="dark"] .subtle,
		:root[data-theme="dark"] .card-title,
		:root[data-theme="dark"] .empty-state,
		:root[data-theme="dark"] .note,
		:root[data-theme="dark"] .small {{
			color: var(--muted);
		}}

		:root[data-theme="dark"] .table-count {{
			color: #dbe8ff;
		}}

		:root[data-theme="dark"] .drag-handle,
		:root[data-theme="dark"] .resize-handle {{
			background: #0f172a;
			color: #e2e8f0;
		}}

		:root[data-theme="dark"] code {{
			background: #0f172a;
			color: #f1f5f9;
		}}

		:root[data-theme="dark"] input::placeholder {{
			color: #8ea0ba;
		}}
	</style>
</head>
<body>
	<div class="page">
		<section class="hero">
			<div class="hero-header">
				<div>
					<h1>LLM Prompt Guard Test Suite Static Catalogue Report</h1>
					<p class="subtle">
						Static inventory view generated from catalogue metadata and AST parsing of test files.
						No tests were executed.
					</p>
				</div>
				<button class="theme-toggle" id="themeToggle" type="button">Dark mode</button>
			</div>
		</section>

		<section class="meta-grid" id="metaGrid"></section>
		<section class="summary-grid" id="summaryGrid"></section>

		<section class="filters-panel">
			<h2 class="section-heading">Catalogue Filters</h2>
			<div class="filters-grid">
				<div>
					<label for="modeFilter">View</label>
					<select id="modeFilter">
						<option value="complete_catalogue">Complete Catalogue</option>
						<option value="unimplemented">Unimplemented</option>
						<option value="invalid_linked_tests">Invalid Linked Tests</option>
						<option value="floating_tests">Floating Tests</option>
						<option value="mismatches">Mismatches</option>
					</select>
				</div>

				<div>
					<label for="searchFilter">Search</label>
					<input id="searchFilter" type="text" placeholder="Search by TC ID, function, file, description, or issue">
				</div>

				<div>
					<label for="levelFilter">Level</label>
					<select id="levelFilter">
						<option value="all">All</option>
					</select>
				</div>

				<div>
					<label for="componentFilter">Component</label>
					<select id="componentFilter">
						<option value="all">All</option>
					</select>
				</div>

				<div>
					<label for="smokeFilter">Smoke</label>
					<select id="smokeFilter">
						<option value="all">All</option>
						<option value="true">True</option>
						<option value="false">False</option>
						<option value="blank">Blank</option>
					</select>
				</div>

				<div>
					<label for="statusFilter">Status</label>
					<select id="statusFilter">
						<option value="all">All</option>
					</select>
				</div>

				<div>
					<label for="fileFilter">File Path</label>
					<select id="fileFilter">
						<option value="all">All</option>
					</select>
				</div>

				<div>
					<label for="issueFilter">Issue</label>
					<select id="issueFilter">
						<option value="all">All</option>
					</select>
				</div>

				<div>
					<label for="duplicateFilter">Duplicate Linkage</label>
					<select id="duplicateFilter">
						<option value="all">All</option>
						<option value="true">True</option>
						<option value="false">False</option>
					</select>
				</div>
			</div>
			<p class="note">
				Mismatches are always calculated using catalogue level against file placement under
				<code>tests/unit/</code>, <code>tests/integration/</code>, and <code>tests/e2e/</code>.
			</p>
		</section>

		<section class="table-panel" id="tableHost"></section>
	</div>

	<script>
		const reportData = {json_blob};
		const themeStorageKey = "promptGuardCatalogueTheme";
		const columnOrderStorageKey = "promptGuardCatalogueColumnOrder";
		const columnWidthStorageKey = "promptGuardCatalogueColumnWidths";
		const tableColumns = [
			{{ key: "status", label: "Status" }},
			{{ key: "tc_id", label: "TC ID" }},
			{{ key: "name", label: "Test Function" }},
			{{ key: "file_path", label: "File Path" }},
			{{ key: "level", label: "Level" }},
			{{ key: "component", label: "Component" }},
			{{ key: "smoke", label: "Smoke" }},
			{{ key: "description", label: "Description" }},
			{{ key: "issues", label: "Issues" }},
		];
		let currentColumnOrder = [];
		let currentColumnWidths = {{}};
		let draggedColumnKey = null;
		let activeResize = null;
		let resizeListenersBound = false;

		function escapeHtml(value) {{
			return String(value)
				.replace(/&/g, "&amp;")
				.replace(/</g, "&lt;")
				.replace(/>/g, "&gt;")
				.replace(/"/g, "&quot;")
				.replace(/'/g, "&#39;");
		}}

		function toDisplayLabel(value) {{
			return String(value || "")
				.replace(/_/g, " ")
				.replace(/\\b\\w/g, c => c.toUpperCase());
		}}

		function badgeList(values, extraClass = "") {{
			if (!values || values.length === 0) return "-";
			return values
				.map(value => `<span class="badge ${{extraClass}}">${{escapeHtml(value)}}</span>`)
				.join("");
		}}

		function statusBadge(status) {{
			const cssClass = "status-" + String(status || "")
				.toLowerCase()
				.replace(/\\s+/g, "-");

			return `<span class="badge ${{cssClass}}">${{escapeHtml(status || "")}}</span>`;
		}}

		function defaultColumnOrder() {{
			return tableColumns.map(column => column.key);
		}}

		function loadColumnOrder() {{
			try {{
				const stored = JSON.parse(localStorage.getItem(columnOrderStorageKey) || "null");
				const keys = Array.isArray(stored) ? stored.filter(key => tableColumns.some(column => column.key === key)) : [];
				const missing = tableColumns.map(column => column.key).filter(key => !keys.includes(key));
				return [...keys, ...missing];
			}}
			catch (error) {{
				return defaultColumnOrder();
			}}
		}}

		function saveColumnOrder(order) {{
			localStorage.setItem(columnOrderStorageKey, JSON.stringify(order));
		}}

		function defaultColumnWidths() {{
			return {{
				status: 132,
				tc_id: 168,
				name: 228,
				file_path: 248,
				level: 168,
				component: 176,
				smoke: 104,
				description: 340,
				issues: 220,
			}};
		}}

		function loadColumnWidths() {{
			const defaults = defaultColumnWidths();

			try {{
				const stored = JSON.parse(localStorage.getItem(columnWidthStorageKey) || "null");
				if (!stored || typeof stored !== "object") {{
					return defaults;
				}}

				const result = {{ ...defaults }};
				for (const column of tableColumns) {{
					const rawValue = stored[column.key];
					const width = Number(rawValue);
					if (Number.isFinite(width) && width >= 96) {{
						result[column.key] = Math.round(width);
					}}
				}}
				return result;
			}}
			catch (error) {{
				return defaults;
			}}
		}}

		function saveColumnWidths(widths) {{
			localStorage.setItem(columnWidthStorageKey, JSON.stringify(widths));
		}}

		function widthForColumn(key) {{
			const value = Number(currentColumnWidths[key]);
			return Number.isFinite(value) && value > 0 ? value : defaultColumnWidths()[key];
		}}

		function moveColumn(order, fromKey, toKey) {{
			const next = order.filter(key => key !== fromKey);
			const targetIndex = next.indexOf(toKey);
			next.splice(targetIndex, 0, fromKey);
			return next;
		}}

		function columnByKey(key) {{
			return tableColumns.find(column => column.key === key);
		}}

		function renderHeaderRow() {{
			return currentColumnOrder.map(key => {{
				const column = columnByKey(key);
				return `
					<th data-column-key="${{column.key}}" style="width: ${{widthForColumn(column.key)}}px;">
						<div class="th-content">
							<span class="drag-handle" title="Drag to reorder columns" draggable="true" data-drag-key="${{column.key}}">⋮⋮</span>
							<span class="th-label">${{escapeHtml(column.label)}}</span>
							<span class="resize-handle" title="Drag to resize column" data-resize-key="${{column.key}}">&#8596;</span>
						</div>
					</th>
				`;
			}}).join("");
		}}

		function renderColumnGroup() {{
			return `
				<colgroup>
					${{currentColumnOrder.map(key => `<col style="width: ${{widthForColumn(key)}}px;">`).join("")}}
				</colgroup>
			`;
		}}

		function renderCell(row, key) {{
			switch (key) {{
				case "status":
					return `<td>${{statusBadge(row.status)}}</td>`;
				case "tc_id":
					return `<td><code>${{escapeHtml(row.tc_id || "")}}</code></td>`;
				case "name":
					return `
						<td>
							${{row.name ? `<code>${{escapeHtml(row.name)}}</code>` : "-"}}
							${{row.nodeid ? `<div class="small">${{escapeHtml(row.nodeid)}}</div>` : ""}}
						</td>
					`;
				case "file_path":
					return `<td>${{row.file_path ? `<code>${{escapeHtml(row.file_path)}}</code>` : "-"}}</td>`;
				case "level":
					return `<td>${{badgeList(row.level)}}</td>`;
				case "component":
					return `<td>${{badgeList(row.component)}}</td>`;
				case "smoke":
					return `<td>${{row.smoke === null || row.smoke === undefined ? "-" : escapeHtml(String(row.smoke))}}</td>`;
				case "description":
					return `<td>${{escapeHtml(row.description || "")}}</td>`;
				case "issues":
					return `<td>${{badgeList(row.issues, "issue-badge")}}</td>`;
				default:
					return "<td>-</td>";
			}}
		}}

		function renderMeta() {{
			const meta = reportData.meta;
			const items = [
				["Catalogue Path", meta.catalogue_path],
				["Tests Root", meta.tests_root],
				["Layout Rule", meta.layout_rule],
			];

			const root = document.getElementById("metaGrid");
			root.innerHTML = items.map(([label, value]) => `
				<div class="card">
					<div class="card-title">${{escapeHtml(label)}}</div>
					<div class="card-value"><code>${{escapeHtml(value)}}</code></div>
				</div>
			`).join("");
		}}

		function renderSummary() {{
			const root = document.getElementById("summaryGrid");
			root.innerHTML = Object.entries(reportData.summary)
				.map(([key, value]) => `
					<div class="card">
						<div class="card-title">${{escapeHtml(toDisplayLabel(key))}}</div>
						<div class="summary-number">${{escapeHtml(value)}}</div>
					</div>
				`)
				.join("");
		}}

		function currentRows() {{
			const mode = document.getElementById("modeFilter").value;
			return reportData.modes[mode] || [];
		}}

		function rebuildOption(selectId, values) {{
			const select = document.getElementById(selectId);
			const previous = select.value;
			const options = ['<option value="all">All</option>'];

			for (const value of values) {{
				options.push(`<option value="${{escapeHtml(value)}}">${{escapeHtml(value)}}</option>`);
			}}

			select.innerHTML = options.join("");

			if ([...select.options].some(option => option.value === previous)) {{
				select.value = previous;
			}}
		}}

		function rebuildDynamicFilters() {{
			const rows = currentRows();

			const levels = new Set();
			const components = new Set();
			const statuses = new Set();
			const files = new Set();
			const issues = new Set();

			for (const row of rows) {{
				(row.level || []).forEach(value => levels.add(value));
				(row.component || []).forEach(value => components.add(value));
				(row.issues || []).forEach(value => issues.add(value));

				if (row.status) statuses.add(row.status);
				if (row.file_path) files.add(row.file_path);
			}}

			rebuildOption("levelFilter", [...levels].sort());
			rebuildOption("componentFilter", [...components].sort());
			rebuildOption("statusFilter", [...statuses].sort());
			rebuildOption("fileFilter", [...files].sort());
			rebuildOption("issueFilter", [...issues].sort());
		}}

		function matchesSearch(row, search) {{
			if (!search) return true;

			const haystack = [
				row.tc_id,
				row.name,
				row.nodeid,
				row.file_path,
				row.description,
				row.status,
				...(row.level || []),
				...(row.component || []),
				...(row.issues || []),
			]
				.filter(Boolean)
				.join(" ")
				.toLowerCase();

			return haystack.includes(search);
		}}

		function valueInList(listValue, selected) {{
			if (selected === "all") return true;
			return Array.isArray(listValue) && listValue.includes(selected);
		}}

		function smokeMatches(rowSmoke, filterValue) {{
			if (filterValue === "all") return true;
			if (filterValue === "blank") return rowSmoke === null || rowSmoke === undefined || rowSmoke === "";
			return String(rowSmoke) === filterValue;
		}}

		function matchesFilters(row) {{
			const search = document.getElementById("searchFilter").value.trim().toLowerCase();
			const level = document.getElementById("levelFilter").value;
			const component = document.getElementById("componentFilter").value;
			const smoke = document.getElementById("smokeFilter").value;
			const status = document.getElementById("statusFilter").value;
			const file = document.getElementById("fileFilter").value;
			const issue = document.getElementById("issueFilter").value;
			const duplicate = document.getElementById("duplicateFilter").value;

			if (!matchesSearch(row, search)) return false;
			if (!valueInList(row.level || [], level)) return false;
			if (!valueInList(row.component || [], component)) return false;
			if (!smokeMatches(row.smoke, smoke)) return false;
			if (status !== "all" && row.status !== status) return false;
			if (file !== "all" && row.file_path !== file) return false;
			if (!valueInList(row.issues || [], issue)) return false;
			if (duplicate === "true" && !row.duplicate) return false;
			if (duplicate === "false" && row.duplicate) return false;

			return true;
		}}

		function renderRows(rows) {{
			if (rows.length === 0) {{
				return `
					<div class="empty-state">
						No rows match the current filters.
					</div>
				`;
			}}

			return `
				<div class="table-shell">
					<div class="table-scrollbar" id="tableScrollbar">
						<div class="table-scrollbar-spacer" id="tableScrollbarSpacer"></div>
					</div>
					<div class="table-wrap" id="tableWrap">
						<table id="catalogueTable">
							${{renderColumnGroup()}}
							<thead>
								<tr>
									${{renderHeaderRow()}}
								</tr>
							</thead>
							<tbody>
								${{rows.map(row => `
									<tr>
										${{currentColumnOrder.map(key => renderCell(row, key)).join("")}}
									</tr>
								`).join("")}}
							</tbody>
						</table>
					</div>
				</div>
			`;
		}}

		function applyTheme(theme) {{
			document.documentElement.dataset.theme = theme;
			localStorage.setItem(themeStorageKey, theme);
			const button = document.getElementById("themeToggle");
			if (button) {{
				button.textContent = theme === "dark" ? "Light mode" : "Dark mode";
			}}
		}}

		function initialiseTheme() {{
			const stored = localStorage.getItem(themeStorageKey);
			const preferred = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
				? "dark"
				: "light";
			applyTheme(stored || preferred);
			document.getElementById("themeToggle").addEventListener("click", () => {{
				const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
				applyTheme(current === "dark" ? "light" : "dark");
			}});
		}}

		function initialiseColumnOrder() {{
			currentColumnOrder = loadColumnOrder();
			saveColumnOrder(currentColumnOrder);
		}}

		function initialiseColumnWidths() {{
			currentColumnWidths = loadColumnWidths();
			saveColumnWidths(currentColumnWidths);
		}}

		function syncTableScrollbars() {{
			const topScrollbar = document.getElementById("tableScrollbar");
			const wrap = document.getElementById("tableWrap");
			const spacer = document.getElementById("tableScrollbarSpacer");

			if (!topScrollbar || !wrap || !spacer) return;

			spacer.style.width = `${{Math.max(wrap.scrollWidth, wrap.clientWidth)}}px`;

			let syncing = false;
			topScrollbar.onscroll = () => {{
				if (syncing) return;
				syncing = true;
				wrap.scrollLeft = topScrollbar.scrollLeft;
				syncing = false;
			}};

			wrap.onscroll = () => {{
				if (syncing) return;
				syncing = true;
				topScrollbar.scrollLeft = wrap.scrollLeft;
				syncing = false;
			}};

			topScrollbar.scrollLeft = wrap.scrollLeft;
		}}

		function bindColumnDragAndDrop() {{
			const table = document.getElementById("catalogueTable");
			if (!table) return;

			table.querySelectorAll(".drag-handle").forEach(handle => {{
				handle.addEventListener("dragstart", event => {{
					draggedColumnKey = event.currentTarget.dataset.dragKey;
					event.dataTransfer.effectAllowed = "move";
					event.dataTransfer.setData("text/plain", draggedColumnKey);
				}});
			}});

			table.querySelectorAll("th").forEach(header => {{
				header.addEventListener("dragover", event => {{
					event.preventDefault();
				}});

				header.addEventListener("dragenter", event => {{
					event.preventDefault();
					header.classList.add("is-drag-over");
				}});

				header.addEventListener("dragleave", () => {{
					header.classList.remove("is-drag-over");
				}});

				header.addEventListener("drop", event => {{
					event.preventDefault();
					header.classList.remove("is-drag-over");

					const targetKey = header.dataset.columnKey;
					const fromKey = draggedColumnKey || event.dataTransfer.getData("text/plain");

					if (!fromKey || !targetKey || fromKey === targetKey) {{
						return;
					}}

					currentColumnOrder = moveColumn(currentColumnOrder, fromKey, targetKey);
					saveColumnOrder(currentColumnOrder);
					renderTable();
				}});
			}});
		}}

		function bindColumnResizing() {{
			const table = document.getElementById("catalogueTable");
			if (!table) return;

			table.querySelectorAll(".resize-handle").forEach(handle => {{
				handle.addEventListener("pointerdown", event => {{
					event.preventDefault();
					event.stopPropagation();

					const key = event.currentTarget.dataset.resizeKey;
					const header = event.currentTarget.closest("th");
					if (!key || !header) return;

					activeResize = {{
						key,
						startX: event.clientX,
						startWidth: header.getBoundingClientRect().width,
					}};

					try {{
						event.currentTarget.setPointerCapture(event.pointerId);
					}}
					catch (error) {{
						// Pointer capture is optional here.
					}}
				}});
			}});

			if (resizeListenersBound) {{
				return;
			}}

			resizeListenersBound = true;
			const clampWidth = width => Math.max(96, Math.min(Math.round(width), 720));

			const finishResize = () => {{
				if (!activeResize) return;
				saveColumnWidths(currentColumnWidths);
				activeResize = null;
				syncTableScrollbars();
			}};

			document.addEventListener("pointermove", event => {{
				if (!activeResize) return;

				const delta = event.clientX - activeResize.startX;
				const nextWidth = clampWidth(activeResize.startWidth + delta);
				currentColumnWidths = {{
					...currentColumnWidths,
					[activeResize.key]: nextWidth,
				}};

				renderTable();
			}});

			document.addEventListener("pointerup", finishResize);
			document.addEventListener("pointercancel", finishResize);
		}}

		function renderTable() {{
			const mode = document.getElementById("modeFilter").value;
			const rows = currentRows().filter(matchesFilters);

			const titleMap = {{
				complete_catalogue: "Complete Catalogue",
				unimplemented: "Unimplemented",
				invalid_linked_tests: "Invalid Linked Tests",
				floating_tests: "Floating Tests",
				mismatches: "Mismatches",
			}};

			const host = document.getElementById("tableHost");
			host.innerHTML = `
				<div class="table-title-row">
					<h2 class="table-title">${{escapeHtml(titleMap[mode] || mode)}}</h2>
					<div class="table-count">${{rows.length}} Rows</div>
				</div>
				${{renderRows(rows)}}
			`;
			bindColumnDragAndDrop();
			bindColumnResizing();
			syncTableScrollbars();
		}}

		function onModeChange() {{
			rebuildDynamicFilters();
			renderTable();
		}}

		function bindControls() {{
			document.getElementById("modeFilter").addEventListener("change", onModeChange);

			for (const id of [
				"searchFilter",
				"levelFilter",
				"componentFilter",
				"smokeFilter",
				"statusFilter",
				"fileFilter",
				"issueFilter",
				"duplicateFilter",
			]) {{
				document.getElementById(id).addEventListener("input", renderTable);
				document.getElementById(id).addEventListener("change", renderTable);
			}}
		}}

		renderMeta();
		renderSummary();
		initialiseTheme();
		initialiseColumnOrder();
		initialiseColumnWidths();
		bindControls();
		rebuildDynamicFilters();
		renderTable();
		window.addEventListener("resize", syncTableScrollbars);
		new MutationObserver(syncTableScrollbars).observe(document.getElementById("tableHost"), {{
			childList: true,
			subtree: true
		}});
		document.addEventListener("dragend", () => {{
			draggedColumnKey = null;
			document.querySelectorAll("th.is-drag-over").forEach(header => header.classList.remove("is-drag-over"));
		}});
	</script>
</body>
</html>
"""


# ==========
# Main entry
# ==========

def main() -> None:
	"""Generate the static HTML catalogue report."""
	catalogue = load_catalogue(CATALOGUE_PATH)
	tests = scan_tests(TESTS_ROOT)
	report_data = build_report_data(catalogue, tests)

	OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
	OUTPUT_PATH.write_text(render_html(report_data), encoding="utf-8")

	print(f"Static catalogue report written to: {OUTPUT_PATH}")


if __name__ == "__main__":
	main()
