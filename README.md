# ClauseMark Backend + Frontend

ClauseMark is a small document analysis app built with FastAPI and a frontend served directly by the backend. It lets you upload a PDF or image, extract text and clauses, and query the processed document using an intelligent agent.

> **Iteration 3:** This version adds security and production polish: filename sanitization, safe frontend rendering, graceful OCR/OpenAI error handling, expanded test coverage, and a cleaner repository state.

## What it does

- Serves a frontend at `/`
- Accepts document uploads (`PDF`, `PNG`, `JPG`, `JPEG`, `TIFF`)
- Detects whether PDFs are text-based or scanned images
- Extracts text with native PDF parsing or OCR
- Groups page text into clauses and builds annotations
- Provides a clause agent endpoint to answer questions or summarize obligations

## Architecture

ClauseMark is designed as a simple service-based backend with a static frontend. The key pieces are:

- `app/main.py` — starts FastAPI and serves the frontend
- `app/api/routes_documents.py` — API routes for upload, processing, OCR, clauses, annotations, and agent queries
- `app/services/pdf_service.py` — PDF parsing and text extraction via PyMuPDF
- `app/services/ocr_service.py` — OCR extraction for scanned PDFs and images
- `app/services/clause_service.py` — groups extracted text into clause blocks
- `app/services/annotation_service.py` — builds page annotation structure for clauses
- `app/services/agent_service.py` — wraps agent query logic using OpenAI
- `app/frontend/` — HTML, CSS, and JS for the Linux-style frontend UI

See the architecture sketch here:

https://excalidraw.com/#json=4ITHogBISZRVJ7GOkfvp8,ly9uhQDqssK-6cdd8N-0og

## Requirements

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed for OCR support
- `OPENAI_API_KEY` set in `.env` to use the agent functionality

## Install

```bash
cd /home/friday/clausemark-backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Environment

Copy the example env file and set your OpenAI key:

```bash
cp env.example .env
```

Then update `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## Run the app

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open the app in a browser:

```text
http://127.0.0.1:8000/
```

## Sample usage flow

1. Open the app in your browser.
2. Upload a PDF or supported image file.
3. Click `Upload` and wait for the file to finish uploading.
4. Click `Process document` to extract clauses.
5. Review the extracted clauses in the UI.
6. Use the agent form to ask a question or request a summary.

## API endpoints

- `POST /documents/upload` - upload a document
- `POST /documents/{document_id}/process` - process the uploaded document
- `GET /documents/{document_id}/clauses` - retrieve extracted clauses
- `GET /documents/{document_id}/annotations` - retrieve page annotations
- `POST /documents/{document_id}/agent` - query the clause agent

## Notes

- The app stores uploaded files in `uploads/` and results in `outputs/`.
- These folders are ignored by `.gitignore`.
- If you do not set `OPENAI_API_KEY`, agent queries will not work, but upload/process features still run.
- If you're on a machine without Tesseract installed, OCR-based processing will fail for scanned PDFs and images.
