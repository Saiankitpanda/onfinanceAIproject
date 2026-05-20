import os
from dotenv import load_dotenv
import logging
import time

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
"""
    }

    return instructions.get(task, instructions["answer_question"])


def run_clause_agent(task: str, clauses: list, question: str | None = None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return "OPENAI_API_KEY is missing. Add it in your .env file to use the agent."

    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return "OpenAI package is not installed. Run: pip install openai"

    if not clauses:
        return "No clauses were provided to the agent."

    try:
        client = OpenAI(api_key=api_key)

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
"""

        # Retry/backoff loop for transient failures
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
                return response.output_text
            except Exception as error:
                last_exc = error
                # Log and decide whether to retry
                logger.exception("Agent call failed on attempt %s", attempt, extra={"task": task})
                if attempt <= max_retries:
                    sleep_time = backoff_base * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                    continue
                else:
                    return f"Agent failed gracefully after retries: {str(last_exc)}"
    except Exception as error:
        logger.exception("Agent setup failed", extra={"error": str(error)})
        return f"Agent failed gracefully: {str(error)}"
