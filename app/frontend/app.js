const uploadForm = document.getElementById("upload-form");
const processButton = document.getElementById("process-button");
const uploadStatus = document.getElementById("upload-status");
const resultSummary = document.getElementById("result-summary");
const clauseList = document.getElementById("clause-list");
const clausesPanel = document.getElementById("clauses-panel");
const agentPanel = document.getElementById("agent-panel");
const agentForm = document.getElementById("agent-form");
const agentAnswer = document.getElementById("agent-answer");

let currentDocumentId = null;

const updateStatus = (message, type = "info") => {
  uploadStatus.textContent = message;
  uploadStatus.style.color = type === "danger" ? "#f97316" : "#cbd5e1";
};

const handleError = async (response) => {
  let message = "Unexpected error.";

  try {
    const payload = await response.json();
    message = payload.detail || payload.message || message;
  } catch (err) {
    message = await response.text();
  }

  updateStatus(message, "danger");
  throw new Error(message);
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
  resultSummary.textContent = "Click Process document to analyze clauses.";
});

processButton.addEventListener("click", async () => {
  if (!currentDocumentId) {
    updateStatus("Upload a document before processing.", "danger");
    return;
  }

  updateStatus("Processing document. This may take a moment...");
  processButton.disabled = true;

  const response = await fetch(`/documents/${currentDocumentId}/process`, {
    method: "POST",
  });

  if (!response.ok) {
    await handleError(response);
  }

  const data = await response.json();
  updateStatus("Document processed successfully.");
  displayResult(data);
  displayClauses(data.clauses);
  agentPanel.hidden = false;
});

agentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!currentDocumentId) {
    updateStatus("Process a document first.", "danger");
    return;
  }

  const task = document.getElementById("agent-task").value.trim();
  const question = document.getElementById("agent-question").value.trim();

  if (!task) {
    updateStatus("Please enter a task for the agent.", "danger");
    return;
  }

  updateStatus("Querying the clause agent...");

  const response = await fetch(`/documents/${currentDocumentId}/agent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ task, question }),
  });

  if (!response.ok) {
    await handleError(response);
  }

  const data = await response.json();
  agentAnswer.textContent = data.answer || "No answer returned.";
  updateStatus("Agent response received.");
});

const displayResult = (data) => {
  resultSummary.innerHTML = `
    <div><strong>Document:</strong> ${data.filename}</div>
    <div><strong>Status:</strong> ${data.status}</div>
    <div><strong>Mode:</strong> ${data.processing_mode}</div>
    <div><strong>Blocks:</strong> ${data.total_blocks}</div>
    <div><strong>Clauses:</strong> ${data.total_clauses}</div>
  `;
};

const displayClauses = (clauses) => {
  clauseList.innerHTML = "";
  clausesPanel.hidden = false;

  if (!clauses.length) {
    clauseList.innerHTML = "<div class=\"status-card\">No clauses were found.</div>";
    return;
  }

  clauses.forEach((clause) => {
    const card = document.createElement("div");
    card.className = "clause-card";
    card.innerHTML = `
      <h3>${clause.clause_id || "No ID"} · ${clause.clause_type}</h3>
      <p>${clause.text}</p>
    `;
    clauseList.appendChild(card);
  });
};

const init = () => {
  uploadStatus.textContent = "Select a document to upload and analyze.";
  resultSummary.textContent = "Upload and process a document to begin.";
};

init();
