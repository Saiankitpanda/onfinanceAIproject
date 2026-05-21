import logging
import os
import re
import time
from typing import Iterable, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("clausemark.agent_service")


def build_clause_context(clauses: list) -> str:
    context = ""

    for clause in clauses:
        clause_id = clause.get("clause_id", "unknown")
        clause_type = clause.get("clause_type", "unknown")
        text = clause.get("text", "")
        page_start = clause.get("page_start", "unknown")
        page_end = clause.get("page_end", "unknown")

        context += f"""
Clause ID: {clause_id}
Clause Type: {clause_type}
Page Range: {page_start} to {page_end}
Text: {text}
---
"""

    return context.strip()


def get_task_instruction(task: str) -> str:
    task = task.lower().strip()

    instructions = {
        "summarize": """
Summarize the circular clearly.
Return 5 to 8 bullet points.
Mention important clause IDs where relevant.
""",
        "explain": """
Explain the requested clause or clauses in simple language.
Use beginner-friendly wording.
Mention the clause ID.
""",
        "answer_question": """
Answer the user's question using only the provided clauses.
Mention clause IDs wherever possible.
If the answer is not present, say that the provided clauses do not contain enough information.
""",
        "extract_obligations": """
Extract all obligations from the clauses.
For each obligation, return:
- Obligation
- Responsible party
- Clause ID
- Page number if available
""",
        "extract_deadlines": """
Extract all dates, timelines, deadlines, effective dates, due dates, or reporting periods.
For each item, return:
- Deadline/date
- Meaning
- Related clause ID
- Page number if available
""",
        "extract_penalties": """
Extract all penalties, consequences, sanctions, fines, or non-compliance actions.
For each item, return:
- Penalty/consequence
- Trigger condition
- Clause ID
- Page number if available
""",
        "validate_clause_boundaries": """
Review whether the detected clauses look structurally correct.
Identify:
- Possible wrongly merged clauses
- Possible missing clause IDs
- Suspiciously long clauses
- Suspiciously short clauses
- Formatting issues
Return practical debugging suggestions.
""",
    }

    return instructions.get(task, instructions["answer_question"])


def _clause_label(clause: dict) -> str:
    clause_id = clause.get("clause_id") or "unknown"
    clause_type = clause.get("clause_type") or "clause"
    return f"Clause {clause_id} ({clause_type})"


def _truncate(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _extract_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _normalize_words(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "shall",
        "must",
        "will",
        "may",
        "are",
        "is",
        "be",
        "to",
        "of",
        "a",
        "an",
        "in",
        "on",
        "by",
        "or",
        "as",
        "at",
        "it",
        "its",
        "their",
        "your",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "please",
        "do",
        "does",
        "did",
    }
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {token for token in tokens if token not in stop_words}


def _find_relevant_clauses(question: str, clauses: List) -> List[dict]:
    question_words = _normalize_words(question)
    if not question_words:
        return clauses[:3]

    matched = []
    for clause in clauses:
        clause_words = _normalize_words(clause.get("text", ""))
        score = len(question_words & clause_words)
        if score > 0:
            matched.append((score, clause))

    matched.sort(key=lambda item: (-item[0], item[1].get("page_start", 0)))
    return [clause for _, clause in matched][:3]


def _format_clause_summary(clauses: Iterable[dict]) -> str:
    lines = []
    for clause in clauses:
        lines.append(f"- {_clause_label(clause)}: {_truncate(clause.get('text', ''), 160)}")
    return "\n".join(lines)


def _build_local_summary(clauses: list) -> str:
    selected = clauses[:5]
    body = _format_clause_summary(selected)
    return (
        f"Local agent summary:\n{body or 'No clause details available.'}\n\n"
        "Why it matters: this answer is built from the extracted clause text, so you can quickly scan the most important points without needing the cloud model."
    )


def _build_local_explanation(clauses: List, question: Optional[str]) -> str:
    if not clauses:
        return "The provided clauses do not contain enough information."

    target = question.strip() if question else ""
    relevant = _find_relevant_clauses(target, clauses) if target else clauses[:2]
    explanation = _format_clause_summary(relevant)
    return (
        f"Local explanation:\n{explanation or 'No relevant clauses found.'}\n\n"
        "Why it matters: the answer stays close to the clause text, so you can map each point back to the document and ask a narrower follow-up if needed."
    )


def _build_local_question_answer(clauses: List, question: Optional[str]) -> str:
    question_text = (question or "").strip()
    if not question_text:
        return _build_local_summary(clauses)

    relevant = _find_relevant_clauses(question_text, clauses)
    if not relevant:
        return "The provided clauses do not contain enough information."

    answer = _format_clause_summary(relevant)
    return (
        f"Answer: {answer or 'No matching clauses were found.'}\n\n"
        f"Explanation: I matched your question against the closest clauses and surfaced the most relevant lines. Question understood: {question_text}"
    )


def _build_obligations(clauses: list) -> str:
    obligation_keywords = ("shall", "must", "required", "need to", "needs to", "should")
    findings = []

    for clause in clauses:
        text = clause.get("text", "")
        for sentence in _extract_sentences(text):
            if any(keyword in sentence.lower() for keyword in obligation_keywords):
                findings.append(
                    f"- {_clause_label(clause)}: {_truncate(sentence, 180)}"
                )

    if not findings:
        return "No explicit obligations were found in the provided clauses."

    return "Extracted obligations:\n" + "\n".join(findings)


def _build_deadlines(clauses: list) -> str:
    deadline_patterns = [
        r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\bwithin\s+\d+\s+(?:days|business days|working days|weeks|months)\b",
        r"\bby\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
    ]
    findings = []

    for clause in clauses:
        text = clause.get("text", "")
        lower_text = text.lower()
        for pattern in deadline_patterns:
            for match in re.finditer(pattern, lower_text, re.IGNORECASE):
                snippet = text[max(0, match.start() - 40) : match.end() + 60]
                findings.append(f"- {_clause_label(clause)}: {_truncate(snippet, 180)}")

    if not findings:
        return "No explicit deadlines or dates were found in the provided clauses."

    return "Extracted deadlines:\n" + "\n".join(findings)


def _build_penalties(clauses: list) -> str:
    penalty_keywords = ("penalty", "fine", "sanction", "consequence", "non-compliance", "non compliance")
    findings = []

    for clause in clauses:
        for sentence in _extract_sentences(clause.get("text", "")):
            if any(keyword in sentence.lower() for keyword in penalty_keywords):
                findings.append(
                    f"- {_clause_label(clause)}: {_truncate(sentence, 180)}"
                )

    if not findings:
        return "No explicit penalties or consequences were found in the provided clauses."

    return "Extracted penalties:\n" + "\n".join(findings)


def _build_validation_notes(clauses: list) -> str:
    notes = [f"Detected {len(clauses)} clause(s)."]

    long_clauses = [c for c in clauses if len((c.get("text") or "").split()) > 220]
    short_clauses = [c for c in clauses if len((c.get("text") or "").split()) < 8]

    if long_clauses:
        notes.append(
            "Possible merged clauses: "
            + ", ".join(_clause_label(clause) for clause in long_clauses[:5])
        )

    if short_clauses:
        notes.append(
            "Very short clauses: "
            + ", ".join(_clause_label(clause) for clause in short_clauses[:5])
        )

    if not long_clauses and not short_clauses:
        notes.append("Clause lengths look broadly reasonable.")

    return "\n".join(f"- {note}" for note in notes)


def _local_agent_response(task: str, clauses: List, question: Optional[str]) -> str:
    normalized_task = task.lower().strip()

    if normalized_task == "summarize":
        return _build_local_summary(clauses)
    if normalized_task == "explain":
        return _build_local_explanation(clauses, question)
    if normalized_task == "answer_question":
        return _build_local_question_answer(clauses, question)
    if normalized_task == "extract_obligations":
        return _build_obligations(clauses)
    if normalized_task == "extract_deadlines":
        return _build_deadlines(clauses)
    if normalized_task == "extract_penalties":
        return _build_penalties(clauses)
    if normalized_task == "validate_clause_boundaries":
        return _build_validation_notes(clauses)

    return _build_local_question_answer(clauses, question)


def _format_cloud_two_paragraph_prompt(task: str, question: Optional[str]) -> str:
    return f"""
Respond in exactly 2 short paragraphs separated by a blank line.

Paragraph 1:
- Give the direct answer first.
- Keep it concise and easy to scan.

Paragraph 2:
- Explain the answer in plain language.
- Mention clause IDs where helpful.
- If there is not enough information, say:
"The provided clauses do not contain enough information."

Task: {task}
Question: {question if question else "No specific question provided."}
"""


def run_clause_agent(task: str, clauses: List, question: Optional[str] = None) -> str:
    if not clauses:
        return "No clauses were provided to the agent."

    api_key = os.getenv("OPENAI_API_KEY")
    use_cloud_model = bool(api_key) and os.getenv("AGENT_USE_OPENAI", "0") == "1"

    clause_context = build_clause_context(clauses)
    task_instruction = get_task_instruction(task)

    system_prompt = """
You are Clause Analysis Agent.

You analyze extracted clauses from circulars, legal documents, regulatory notices, and scanned PDFs.

Strict rules:
1. Use only the clause text provided.
2. Do not invent clauses.
3. Do not use outside knowledge.
4. Do not assume missing information.
5. Mention clause IDs wherever possible.
6. If the provided clauses do not contain enough information, say:
"The provided clauses do not contain enough information."
7. Keep the answer clear, structured, and easy to understand.
"""

    user_prompt = f"""
Task:
{task}

Task Instruction:
{task_instruction}

User Question:
{question if question else "No specific question provided."}

Extracted Clauses:
{clause_context}

Formatting Reminder:
{_format_cloud_two_paragraph_prompt(task, question)}
"""

    if use_cloud_model:
        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            logger.warning("OpenAI package not installed; using local agent fallback.")
        else:
            try:
                client = OpenAI(api_key=api_key)
                max_retries = int(os.getenv("AGENT_MAX_RETRIES", "2"))
                backoff_base = float(os.getenv("AGENT_BACKOFF_BASE", "1"))
                last_exc = None

                for attempt in range(1, max_retries + 2):
                    try:
                        response = client.responses.create(
                            model="gpt-4.1-mini",
                            input=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        )
                        output_text = getattr(response, "output_text", "").strip()
                        if output_text:
                            return output_text
                        logger.warning(
                            "OpenAI response was empty; falling back to local agent."
                        )
                        break
                    except Exception as error:
                        last_exc = error
                        logger.exception(
                            "Agent call failed on attempt %s", attempt, extra={"task": task}
                        )
                        if attempt <= max_retries:
                            time.sleep(backoff_base * (2 ** (attempt - 1)))
                            continue
                        logger.warning(
                            "OpenAI call failed after retries; using local fallback."
                        )
                        break

                if last_exc:
                    logger.info("OpenAI fallback reason: %s", last_exc)
            except Exception as error:
                logger.exception("Agent setup failed", extra={"error": str(error)})

    return _local_agent_response(task, clauses, question)
