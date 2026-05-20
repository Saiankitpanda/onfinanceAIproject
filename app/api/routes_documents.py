from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict
import os
import shutil
import uuid
import json

from app.services.pdf_service import is_text_pdf, extract_text_blocks_from_pdf
from app.services.ocr_service import ocr_image_file, ocr_pdf_file
from app.services.clause_service import group_blocks_into_clauses
from app.services.annotation_service import (
    enrich_clauses_with_annotations,
    build_page_annotations
)
from app.services.agent_service import run_clause_agent
from app.utils.file_utils import sanitize_filename, is_allowed_magic
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "200/minute")
RATE_LIMIT_AGENT = os.getenv("RATE_LIMIT_AGENT", "10/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])

logger = logging.getLogger("clausemark.routes_documents")


router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10 MB default


class AgentRequest(BaseModel):
    task: str
    question: str | None = None


class OcrBlocksResponse(BaseModel):
    document_id: str
    filename: str | None = None
    processing_mode: str
    total_blocks: int
    blocks: List[Dict]


@router.get("/readiness")
def get_readiness():
    tesseract_path = shutil.which("tesseract")
    openai_ready = bool(os.getenv("OPENAI_API_KEY"))

    return {
        "status": "ready" if tesseract_path else "partial",
        "checks": {
            "tesseract": {
                "available": bool(tesseract_path),
                "path": tesseract_path,
                "message": (
                    "OCR is available for scanned PDFs and images."
                    if tesseract_path
                    else "Install Tesseract OCR before processing scanned PDFs or images."
                ),
            },
            "openai_api_key": {
                "available": openai_ready,
                "message": (
                    "Agent features are available."
                    if openai_ready
                    else "Set OPENAI_API_KEY in .env to enable agent responses."
                ),
            },
        },
        "demo_flow": [
            "Upload a clean RBI or legal-style PDF with numbered clauses.",
            "Click Process document and confirm the extraction mode, block count, and clause count.",
            "Open Clauses to show structured clause extraction.",
            "Open OCR to show the raw text blocks used by the pipeline.",
            "Ask the agent to summarize obligations, deadlines, or penalties.",
        ],
    }


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]

    filename = sanitize_filename(file.filename)
    extension = os.path.splitext(filename)[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    document_upload_dir = os.path.join(UPLOAD_DIR, document_id)
    document_output_dir = os.path.join(OUTPUT_DIR, document_id)

    os.makedirs(document_upload_dir, exist_ok=True)
    os.makedirs(document_output_dir, exist_ok=True)

    saved_file_path = os.path.join(document_upload_dir, filename)

    # Fast-fail if Content-Length header declares a size larger than the limit
    try:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            if int(content_length) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail="Uploaded file is too large")
    except ValueError:
        # ignore invalid header and continue to streaming
        pass

    # Stream upload and enforce size limit
    size = 0
    try:
        with open(saved_file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    # remove partial file
                    try:
                        f.close()
                    except Exception:
                        pass
                    try:
                        os.remove(saved_file_path)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail="Uploaded file is too large")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as error:
        # Cleanup and propagate as server error
        try:
            os.remove(saved_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {error}")

    # Basic magic-bytes validation to avoid content-type spoofing
    if not is_allowed_magic(saved_file_path, allowed_extensions):
        try:
            os.remove(saved_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Uploaded file content does not match declared file type")

    metadata = {
        "document_id": document_id,
        "filename": filename,
        "file_path": saved_file_path,
        "file_type": extension,
        "status": "uploaded"
    }

    metadata_path = os.path.join(document_output_dir, "metadata.json")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


@router.post("/{document_id}/process")
def process_document(document_id: str):
    metadata_path = os.path.join(OUTPUT_DIR, document_id, "metadata.json")

    if not os.path.exists(metadata_path):
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    file_path = metadata["file_path"]
    file_type = metadata["file_type"]

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Uploaded file not found"
        )

    try:
        if file_type == ".pdf":
            if is_text_pdf(file_path):
                extraction_mode = "pdf_text"
                blocks = extract_text_blocks_from_pdf(file_path)
            else:
                extraction_mode = "ocr_pdf"
                blocks = ocr_pdf_file(file_path)
        else:
            extraction_mode = "ocr_image"
            blocks = ocr_image_file(file_path)
    except Exception as error:
        # Graceful handling: record the extraction error, continue with empty blocks
        extraction_mode = "extraction_error"
        blocks = []
        extraction_error = str(error)
        logger.exception("Document extraction failed", extra={"document_id": document_id, "error": extraction_error})

    # Save raw OCR/text blocks to outputs/{document_id}/ocr_blocks.json
    ocr_output_path = os.path.join(OUTPUT_DIR, document_id, "ocr_blocks.json")
    ocr_payload = {
        "document_id": document_id,
        "filename": metadata.get("filename"),
        "processing_mode": extraction_mode,
        "total_blocks": len(blocks),
        "blocks": blocks,
    }

    # If there was an extraction error, include it in the OCR payload
    if 'extraction_error' in locals():
        ocr_payload["error"] = extraction_error

    try:
        with open(ocr_output_path, "w") as f:
            json.dump(ocr_payload, f, indent=2)
    except Exception:
        # Do not fail the whole processing if saving OCR blocks fails; continue
        pass

    try:
        clauses_raw = group_blocks_into_clauses(blocks)
        clauses = enrich_clauses_with_annotations(clauses_raw)
        annotations = build_page_annotations(clauses)
    except Exception as error:
        # Graceful handling: return partial result with clause processing error
        clause_error = str(error)
        logger.exception("Clause processing failed", extra={"document_id": document_id, "error": clause_error})
        result = {
            "document_id": document_id,
            "filename": metadata["filename"],
            "status": "clause_processing_failed",
            "processing_mode": extraction_mode,
            "total_blocks": len(blocks),
            "total_clauses": 0,
            "clauses": [],
            "pages": [],
            "error": clause_error,
        }

        output_path = os.path.join(OUTPUT_DIR, document_id, "clauses.json")
        try:
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        return result

    result = {
        "document_id": document_id,
        "filename": metadata["filename"],
        "status": "processed",
        "processing_mode": extraction_mode,
        "total_blocks": len(blocks),
        "total_clauses": len(clauses),
        "clauses": clauses,
        "pages": annotations
    }

    output_path = os.path.join(OUTPUT_DIR, document_id, "clauses.json")

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


@router.get("/{document_id}/clauses")
def get_clauses(document_id: str):
    output_path = os.path.join(OUTPUT_DIR, document_id, "clauses.json")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="Clauses not found. Process the document first."
        )

    with open(output_path, "r") as f:
        return json.load(f)


@router.get("/{document_id}/annotations")
def get_annotations(document_id: str):
    output_path = os.path.join(OUTPUT_DIR, document_id, "clauses.json")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="Annotations not found. Process the document first."
        )

    with open(output_path, "r") as f:
        data = json.load(f)

    return {
        "document_id": document_id,
        "pages": data.get("pages", [])
    }


@router.get("/{document_id}/ocr", response_model=OcrBlocksResponse, summary="Get OCR/text blocks", response_description="Raw OCR/text blocks extracted from the uploaded document")
def get_ocr_blocks(document_id: str):
    """Return raw OCR/text blocks saved during processing.

    The response contains the document id, filename, processing mode,
    total number of blocks and the raw `blocks` array produced by the
    extractor (PyMuPDF or OCR).
    """
    ocr_path = os.path.join(OUTPUT_DIR, document_id, "ocr_blocks.json")

    if not os.path.exists(ocr_path):
        raise HTTPException(
            status_code=404,
            detail="OCR/text blocks not found. Process the document first."
        )

    with open(ocr_path, "r") as f:
        return json.load(f)


@router.post("/{document_id}/agent")
@limiter.limit(RATE_LIMIT_AGENT)
def ask_agent(document_id: str, request: AgentRequest):
    output_path = os.path.join(OUTPUT_DIR, document_id, "clauses.json")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="Clauses not found. Process the document before using the agent."
        )

    with open(output_path, "r") as f:
        data = json.load(f)

    clauses = data.get("clauses", [])

    if not clauses:
        raise HTTPException(
            status_code=400,
            detail="No clauses available for agent analysis."
        )

    try:
        answer = run_clause_agent(
            task=request.task,
            clauses=clauses,
            question=request.question,
        )
        agent_status = "ok"
        # Agent helper returns friendly messages on missing API key or package
        if isinstance(answer, str) and (
            answer.lower().startswith("openai_api_key is missing")
            or answer.lower().startswith("openai package")
            or answer.lower().startswith("agent failed gracefully")
        ):
            agent_status = "error"
    except Exception as error:
        answer = f"Agent invocation failed: {str(error)}"
        agent_status = "error"
        logger.exception("Agent invocation failed", extra={"document_id": document_id, "task": request.task, "error": str(error)})

    return {
        "document_id": document_id,
        "task": request.task,
        "question": request.question,
        "answer": answer,
        "agent_status": agent_status,
    }
