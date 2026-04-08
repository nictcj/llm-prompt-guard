const elements = {
	actionSelect: document.getElementById("actionSelect"),
	secretInput: document.getElementById("secretInput"),
	promptInput: document.getElementById("promptInput"),
	sendButton: document.getElementById("sendButton"),
	promptDisplay: document.getElementById("promptDisplay"),
	guardStatus: document.getElementById("guardStatus"),
	modelResponse: document.getElementById("modelResponse"),
	statusText: document.getElementById("statusText"),

	pageTitle: document.getElementById("pageTitle"),
	mainHeading: document.getElementById("mainHeading"),
	mainDescription: document.getElementById("mainDescription"),
	responseHeading: document.getElementById("responseHeading"),

	actionLabel: document.getElementById("actionLabel"),
	secretLabel: document.getElementById("secretLabel"),
	promptLabel: document.getElementById("promptLabel"),
	promptDisplayLabel: document.getElementById("promptDisplayLabel"),
	guardStatusLabel: document.getElementById("guardStatusLabel"),
	modelResponseLabel: document.getElementById("modelResponseLabel")
};

const API_URL = "http://127.0.0.1:8000/api/chat";
let UI_STRINGS = null;

async function loadStrings() {
	const response = await fetch("./strings.json");

	if (!response.ok) {
		throw new Error("Failed to load strings.json");
	}

	return await response.json();
}

function applyStrings(strings) {
	elements.pageTitle.textContent = strings.pageTitle;
	elements.mainHeading.textContent = strings.mainHeading;
	elements.mainDescription.textContent = strings.mainDescription;
	elements.responseHeading.textContent = strings.responseHeading;

	elements.actionLabel.textContent = strings.labels.action;
	elements.secretLabel.textContent = strings.labels.secret;
	elements.promptLabel.textContent = strings.labels.prompt;
	elements.promptDisplayLabel.textContent = strings.labels.prompt;
	elements.guardStatusLabel.textContent = strings.labels.guardStatus;
	elements.modelResponseLabel.textContent = strings.labels.modelResponse;

	elements.sendButton.textContent = strings.buttons.send;

	elements.actionSelect.options[0].textContent = strings.actions.define_secret;
	elements.actionSelect.options[1].textContent = strings.actions.chat;

	elements.promptDisplay.textContent = strings.display.noPromptYet;
	elements.guardStatus.textContent = strings.display.emptyValue;
	elements.modelResponse.textContent = strings.display.emptyValue;
}

function updateFieldState() {
	const action = elements.actionSelect.value;

	if (action === "define_secret") {
		elements.secretInput.disabled = false;
		elements.secretInput.placeholder = UI_STRINGS.placeholders.secretEnabled;

		elements.promptInput.disabled = true;
		elements.promptInput.value = "";
		elements.promptInput.placeholder = UI_STRINGS.placeholders.promptDisabled;
	}
	else {
		elements.secretInput.disabled = true;
		elements.secretInput.value = "";
		elements.secretInput.placeholder = UI_STRINGS.placeholders.secretDisabled;

		elements.promptInput.disabled = false;
		elements.promptInput.placeholder = UI_STRINGS.placeholders.promptEnabled;
	}
}

async function sendPrompt() {
	const action = elements.actionSelect.value;
	const prompt = elements.promptInput.value.trim();
	const secret = elements.secretInput.value.trim();

	if (action === "define_secret" && !secret) {
		elements.statusText.textContent = UI_STRINGS.validation.missingSecret;
		elements.statusText.className = "status error";
		return;
	}
	else if (action === "chat" && !prompt) {
		elements.statusText.textContent = UI_STRINGS.validation.missingPrompt;
		elements.statusText.className = "status error";
		return;
	}

	elements.statusText.textContent = UI_STRINGS.display.loadingStatus;
	elements.statusText.className = "status";

	elements.promptDisplay.textContent = action === "define_secret"
		? UI_STRINGS.display.defineSecretPrompt
		: prompt;

	elements.guardStatus.textContent = "...";
	elements.modelResponse.textContent = UI_STRINGS.display.waitingResponse;

	try {
		const response = await fetch(API_URL, {
			method: "POST",
			headers: {
				"Content-Type": "application/json"
			},
			body: JSON.stringify({
				action: action,
				prompt: prompt || null,
				secret: secret || null
			})
		});

		const data = await response.json();

		if (!response.ok) {
			throw new Error(JSON.stringify(data, null, 2));
		}

		elements.promptDisplay.textContent = data.prompt || (
			action === "define_secret"
				? UI_STRINGS.display.defineSecretPrompt
				: prompt
		);

		elements.guardStatus.textContent = data.guard_status || UI_STRINGS.display.emptyValue;
		elements.modelResponse.textContent = data.response || UI_STRINGS.display.emptyValue;

		if (elements.guardStatus.textContent === UI_STRINGS.guardStates.active) {
			elements.statusText.textContent = UI_STRINGS.statusMessages.success;
			elements.statusText.className = "status success";
		}
		else if (elements.guardStatus.textContent === UI_STRINGS.guardStates.broken) {
			elements.statusText.textContent = UI_STRINGS.statusMessages.guardBroken;
			elements.statusText.className = "status error";
		}
		else {
			elements.statusText.textContent = UI_STRINGS.statusMessages.genericError;
			elements.statusText.className = "status error";
		}
	}
	catch (error) {
		elements.statusText.textContent = UI_STRINGS.statusMessages.requestFailed;
		elements.statusText.className = "status error";
		elements.guardStatus.textContent = UI_STRINGS.display.emptyValue;
		elements.modelResponse.textContent = error.message;
	}
}

async function initialisePage() {
	try {
		UI_STRINGS = await loadStrings();

		applyStrings(UI_STRINGS);

		elements.sendButton.addEventListener("click", sendPrompt);
		elements.actionSelect.addEventListener("change", updateFieldState);

		updateFieldState();
	}
	catch (error) {
		elements.statusText.textContent = error.message;
		elements.statusText.className = "status error";
	}
}

initialisePage();