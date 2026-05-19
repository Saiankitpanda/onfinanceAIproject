# ClauseMark Backend + Frontend

A FastAPI backend with a built-in frontend for uploading documents, extracting clauses, and querying them with an agent.

## Requirements

- Python 3.10+
- Tesseract OCR installed for image/PDF OCR support
- `OPENAI_API_KEY` in `.env` if you want to use the agent endpoint

## Install

```bash
cd /home/friday/clausemark-backend
python3 -m pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Then open `http://127.0.0.1:8000/` in your browser.

## Notes

- Add your OpenAI key to `.env` or copy `env.example`.
- `.env`, `uploads/`, `outputs/`, and `venv/` are ignored by `.gitignore`.
