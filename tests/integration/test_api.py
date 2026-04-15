import pytest


@pytest.mark.tc_id("TC_API_VALID_REQUEST")
def test_api_valid_request(api_client):
	response = api_client.post("/api/chat", json={
		"action": "chat",
		"prompt": "Hello there",
		"secret": None,
	})

	assert response.status_code == 200
	data = response.json()
	assert data["prompt"] == "Hello there"
	assert data["guard_status"] == "Guard is active."
	assert data["response"] == "This is just a normal response."


@pytest.mark.tc_id("TC_API_INVALID_REQUEST")
def test_api_invalid_request(api_client):
	response = api_client.post("/api/chat", json={
		"prompt": "Hello there",
	})

	assert response.status_code == 422


@pytest.mark.tc_id("TC_API_UNSUPPORTED_ACTION")
def test_api_unsupported_action(api_client):
	response = api_client.post("/api/chat", json={
		"action": "dance",
		"prompt": "Hello there",
		"secret": None,
	})

	assert response.status_code == 200
	data = response.json()
	assert data["guard_status"] == "Operation not allowed."
	assert data["response"] == "Unsupported action."
