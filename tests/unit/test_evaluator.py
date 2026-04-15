import pytest


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


@pytest.mark.tc_id("TC_EVL_RESPONSE_NULL")
def test_evaluator_response_null(evaluator):
	secret = "Secret"
	response = None
	ev = evaluator(secret)
	assert not ev.secret_exposed(response)
