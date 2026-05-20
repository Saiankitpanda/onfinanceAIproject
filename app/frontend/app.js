const uploadForm = document.getElementById("upload-form");
const processButton = document.getElementById("process-button");
const uploadStatus = document.getElementById("upload-status");
const resultSummary = document.getElementById("result-summary");
const clauseList = document.getElementById("clause-list");
const clausesPanel = document.getElementById("clauses-panel");
const agentPanel = document.getElementById("agent-panel");
const agentForm = document.getElementById("agent-form");
const agentAnswer = document.getElementById("agent-answer");
const ocrPanel = document.getElementById("ocr-panel");
const ocrButton = document.getElementById("ocr-button");
const ocrOutput = document.getElementById("ocr-output");
const ocrDownload = document.getElementById("ocr-download");
const readinessStatus = document.getElementById("readiness-status");

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
  resultSummary.innerHTML = `
    <div><strong>Document:</strong> ${data.filename}</div>
    <div><strong>Status:</strong> uploaded</div>
    <div><strong>Document ID:</strong> ${data.document_id}</div>
    <div class="muted" style="margin-top:10px">Next: open Upload and click Process document.</div>
  `;
  showView("result");
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
  showView("result");
  agentPanel.hidden = false;
  if (ocrPanel) ocrPanel.hidden = false;
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

    readinessStatus.innerHTML = `
      <div><strong>OCR:</strong> ${tesseract.message}</div>
      <div><strong>Tesseract:</strong> ${tesseract.available ? tesseract.path : "Not found"}</div>
      <div><strong>Agent:</strong> ${openai.message}</div>
    `;
  } catch (error) {
    readinessStatus.textContent = "Unable to load readiness checks.";
  }
};

const initNavigation = () => {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.target));
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

// OCR panel: load OCR blocks and show JSON
if (ocrButton) {
  ocrButton.addEventListener("click", async () => {
    if (!currentDocumentId) {
      updateStatus("Process a document first.", "danger");
      return;
    }

    updateStatus("Loading OCR blocks...");

    const resp = await fetch(`/documents/${currentDocumentId}/ocr`);
    if (!resp.ok) {
      try {
        await handleError(resp);
      } catch (err) {
        // already handled
      }
      return;
    }

    const data = await resp.json();
    if (ocrOutput) ocrOutput.textContent = JSON.stringify(data, null, 2);
    updateStatus("OCR blocks loaded.");

    // enable download link
    if (ocrDownload) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      ocrDownload.href = url;
      ocrDownload.download = `${currentDocumentId}_ocr_blocks.json`;
      ocrDownload.hidden = false;
    }
  });
}
