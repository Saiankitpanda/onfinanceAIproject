const uploadForm = document.getElementById("upload-form");
const processButton = document.getElementById("process-button");
const uploadStatus = document.getElementById("upload-status");
const resultSummary = document.getElementById("result-summary");
const clauseList = document.getElementById("clause-list");
const clausesPanel = document.getElementById("clauses-panel");
const agentPanel = document.getElementById("agent-panel");
const agentForm = document.getElementById("agent-form");
const agentSubmitButton = agentForm?.querySelector("button[type='submit']");
const agentAnswer = document.getElementById("agent-answer");
const ocrPanel = document.getElementById("ocr-panel");
const ocrButton = document.getElementById("ocr-button");
const ocrOutput = document.getElementById("ocr-output");
const ocrDownload = document.getElementById("ocr-download");
const readinessStatus = document.getElementById("readiness-status");

let currentDocumentId = null;
let lastAgentPayload = null;

const clearElement = (element) => {
  if (element) element.replaceChildren();
};

const appendField = (container, label, value) => {
  const row = document.createElement("div");
  const labelNode = document.createElement("strong");
  labelNode.textContent = `${label}: `;
  row.append(labelNode, document.createTextNode(String(value ?? "")));
  container.appendChild(row);
};

const appendMutedText = (container, text) => {
  const row = document.createElement("div");
  row.className = "muted inline-note";
  row.textContent = text;
  container.appendChild(row);
};

const updateStatus = (message, type = "info") => {
  uploadStatus.textContent = message;
  uploadStatus.style.color = type === "danger" ? "#f97316" : "#cbd5e1";
};

const setButtonState = (button, busy, label) => {
  if (!button) return;

  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = label || button.textContent;
    button.disabled = true;
  } else {
    button.disabled = false;
    button.textContent = button.dataset.originalText || button.textContent;
  }
};

const renderActionError = (container, message, retryText, retryCallback) => {
  clearElement(container);
  appendMutedText(container, message);

  if (retryCallback) {
    const retryBtn = document.createElement("button");
    retryBtn.className = "button secondary";
    retryBtn.textContent = retryText;
    retryBtn.addEventListener("click", retryCallback);
    container.appendChild(retryBtn);
  }
};

const handleError = async (response, retryText = null, retryCallback = null, container = resultSummary) => {
  let message = "Unexpected error.";

  try {
    const payload = await response.json();
    message = payload.detail || payload.message || message;
  } catch (err) {
    message = await response.text();
  }

  updateStatus(message, "danger");
  renderActionError(container, message, retryText || "Retry", retryCallback);
  throw new Error(message);
};

const renderJsonSafely = (elementId, data) => {
  const element = document.getElementById(elementId);
  if (!element) return;
  element.textContent = JSON.stringify(data, null, 2);
};

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const fileInput = document.getElementById("document-file");

  if (!fileInput.files.length) {
    updateStatus("Please choose a file first.", "danger");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  updateStatus("Uploading file...");

  const response = await fetch("/documents/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    await handleError(response);
  }

  const data = await response.json();
  currentDocumentId = data.document_id;
  processButton.disabled = false;
  updateStatus(`Uploaded as ${data.filename}. Ready to process.`);
  clearElement(resultSummary);
  appendField(resultSummary, "Document", data.filename);
  appendField(resultSummary, "Status", "uploaded");
  appendField(resultSummary, "Document ID", data.document_id);
  appendMutedText(resultSummary, "Next: open Upload and click Process document.");
  showView("result");
});

const processDocument = async () => {
  if (!currentDocumentId) {
    updateStatus("Upload a document before processing.", "danger");
    return;
  }

  updateStatus("Processing document. This may take a moment...");
  setButtonState(processButton, true, "Processing...");

  try {
    const response = await fetch(`/documents/${currentDocumentId}/process`, {
      method: "POST",
    });

    if (!response.ok) {
      await handleError(response, "Retry processing", processDocument, resultSummary);
      return;
    }

    const data = await response.json();
    if (data.error) {
      updateStatus(`Processing completed with errors: ${data.error}`, "danger");
    } else {
      updateStatus("Document processed successfully.");
    }
    displayResult(data);
    displayClauses(data.clauses);
    showView("result");
    agentPanel.hidden = false;
    if (ocrPanel) ocrPanel.hidden = false;
  } finally {
    setButtonState(processButton, false);
  }
};

processButton.addEventListener("click", processDocument);

const submitAgentRequest = async (payload) => {
  if (!currentDocumentId) {
    updateStatus("Process a document first.", "danger");
    return;
  }

  if (!payload || !payload.task) {
    updateStatus("Please enter a task for the agent.", "danger");
    return;
  }

  updateStatus("Querying the clause agent...");
  setButtonState(agentSubmitButton, true, "Querying...");
  clearElement(agentAnswer);

  try {
    const response = await fetch(`/documents/${currentDocumentId}/agent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      await handleError(response, "Retry agent", () => submitAgentRequest(payload), agentAnswer);
      return;
    }

    const data = await response.json();
    agentAnswer.textContent = data.answer || "No answer returned.";
    if (data.agent_status && data.agent_status === "error") {
      updateStatus("Agent returned an error. See details below.", "danger");
      renderActionError(agentAnswer, data.answer || "Agent error occurred.", "Retry agent", () => submitAgentRequest(payload));
    } else {
      updateStatus("Agent response received.");
    }
  } finally {
    setButtonState(agentSubmitButton, false);
  }
};

agentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const task = document.getElementById("agent-task").value.trim();
  const question = document.getElementById("agent-question").value.trim();

  if (!task) {
    updateStatus("Please enter a task for the agent.", "danger");
    return;
  }

  lastAgentPayload = { task, question };
  await submitAgentRequest(lastAgentPayload);
});

const displayResult = (data) => {
  clearElement(resultSummary);
  appendField(resultSummary, "Document", data.filename);
  appendField(resultSummary, "Status", data.status);
  appendField(resultSummary, "Mode", data.processing_mode);
  appendField(resultSummary, "Blocks", data.total_blocks);
  appendField(resultSummary, "Clauses", data.total_clauses);
  if (data.error) {
    appendMutedText(resultSummary, `Error: ${data.error}`);
  }
};

const displayClauses = (clauses) => {
  clearElement(clauseList);
  clausesPanel.hidden = false;

  if (!clauses.length) {
    const empty = document.createElement("div");
    empty.className = "status-card";
    empty.textContent = "No clauses were found.";
    clauseList.appendChild(empty);
    return;
  }

  clauses.forEach((clause) => {
    const card = document.createElement("div");
    card.className = "clause-card";

    const heading = document.createElement("h3");
    heading.textContent = `${clause.clause_id || "No ID"} - ${clause.clause_type}`;

    const text = document.createElement("p");
    text.textContent = clause.text || "";

    card.append(heading, text);
    clauseList.appendChild(card);
  });
};

const showView = (target) => {
  const views = {
    upload: document.getElementById("view-upload"),
    result: document.getElementById("view-result"),
    clauses: document.getElementById("view-clauses"),
    agent: document.getElementById("view-agent"),
    ocr: document.getElementById("view-ocr"),
    demo: document.getElementById("view-demo"),
  };

  Object.values(views).forEach((view) => {
    if (view) view.classList.add("hidden");
  });

  const selectedView = views[target] || views.upload;
  selectedView.classList.remove("hidden");

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.target === target);
  });
};

const loadReadiness = async () => {
  if (!readinessStatus) return;

  try {
    const response = await fetch("/documents/readiness");

    if (!response.ok) {
      readinessStatus.textContent = "Unable to load readiness checks.";
      return;
    }

    const data = await response.json();
    const tesseract = data.checks.tesseract;
    const openai = data.checks.openai_api_key;

    clearElement(readinessStatus);
    appendField(readinessStatus, "OCR", tesseract.message);
    appendField(readinessStatus, "Tesseract", tesseract.available ? tesseract.path : "Not found");
    appendField(readinessStatus, "Agent", openai.message);
  } catch (error) {
    readinessStatus.textContent = "Unable to load readiness checks.";
  }
};

const initNavigation = () => {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = button.dataset.target;
      showView(target);

      if (target === "ocr") {
        await loadOcrBlocks();
      }
    });
  });
};

const init = () => {
  uploadStatus.textContent = "Select a document to upload and analyze.";
  resultSummary.textContent = "Upload and process a document to begin.";
  initNavigation();
  loadReadiness();
  showView("demo");
};

init();

const loadOcrBlocks = async () => {
  if (!currentDocumentId) {
    updateStatus("Please upload and process a document first.", "danger");
    return;
  }

  updateStatus("Loading OCR blocks...");

  const resp = await fetch(`/documents/${currentDocumentId}/ocr`);

  if (!resp.ok) {
    try {
      await handleError(resp);
    } catch (err) {
      // Error already displayed
    }
    return;
  }

  const data = await resp.json();
  renderJsonSafely("ocr-output", data);
  updateStatus("OCR blocks loaded.");

  if (ocrDownload) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    ocrDownload.href = url;
    ocrDownload.download = `${currentDocumentId}_ocr_blocks.json`;
    ocrDownload.hidden = false;
  }
};

if (ocrButton) {
  ocrButton.addEventListener("click", loadOcrBlocks);
}
