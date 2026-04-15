from pathlib import Path

import pytest
import yaml


@pytest.mark.tc_id("TC_HAR_ARTIFACT_UPLOAD")
def test_har_artifact_paths_are_consistent():
	workflow_path = Path(".github/workflows/ci.yaml")
	workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

	job_steps = workflow["jobs"]["test"]["steps"]

	backend_step = next(step for step in job_steps if step.get("name") == "Start FastAPI backend")
	web_step = next(step for step in job_steps if step.get("name") == "Start webserver")
	upload_step = next(step for step in job_steps if step.get("name") == "Upload test artifacts")

	assert "test-artifacts/backend.log" in backend_step["run"]
	assert "../test-artifacts/web.log" in web_step["run"]
	assert upload_step["with"]["path"].strip() == "test-artifacts/"
