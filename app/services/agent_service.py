"""
Clause agent service with clause citation and automatic risk flagging.

Public functions:
- query_agent(question, clauses) -> AnswerResult
- flag_risky_clauses(clauses) -> list[RiskFlag]

Both functions use the OpenAI v1.x client when OPENAI_API_KEY is set and
fall back to local keyword-based behavior when it is not.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class AnswerResult:
    answer: str
    source_clause_indices: list[int] = field(default_factory=list)
    confidence: str = "medium"


@dataclass
class RiskFlag:
    clause_index: int
    clause_preview: str
    risk_type: str
    severity: str
    reason: str


_ANSWER_SYSTEM = """You are a contract analysis assistant.
You will be given a numbered list of clauses extracted from a document,
then a user question.

Respond ONLY with a JSON object - no markdown, no preamble - in this exact shape:
{
  "answer": "<your answer in plain English>",
  "source_clause_indices": [<list of 0-based clause indices you used>],
  "confidence": "<high|medium|low>"
}

Rules:
- Base your answer strictly on the provided clauses.
- If no clause is relevant, return an empty list for source_clause_indices
  and set confidence to "low".
- Keep the answer concise (2-4 sentences max).
- Do not make up information not present in the clauses."""

_RISK_SYSTEM = """You are a contract risk analyst.
You will be given a numbered list of clauses extracted from a document.

Identify clauses that contain legal or financial risk. Flag only genuine risks -
do not flag standard boilerplate that poses no unusual risk.

Respond ONLY with a JSON array - no markdown, no preamble - in this exact shape:
[
  {
    "clause_index": <0-based index>,
    "risk_type": "<short category e.g. indemnity | auto-renewal | liability-waiver | penalty>",
    "severity": "<high|medium|low>",
    "reason": "<one sentence explaining the risk>"
  }
]

If there are no risky clauses, return an empty array [].
Severity guide:
  high   - could result in significant financial loss or legal liability
  medium - unusual terms worth negotiating
  low    - standard but worth being aware of"""


def _build_clause_list(clauses: list[dict]) -> str:
    lines = []
    for index, clause in enumerate(clauses):
        text = clause.get("text", "").strip()
        if text:
            lines.append(f"[{index}] {text}")
    return "\n\n".join(lines)


def _call_openai(system: str, user_content: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content.strip()


def _parse_json(raw: str, fallback):
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[: -len("```")].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed. Raw response: %s", raw[:300])
        return fallback


def _local_answer(question: str, clauses: list[dict]) -> AnswerResult:
    keywords = [
        word.lower()
        for word in re.findall(r"[a-z0-9]+", question, flags=re.IGNORECASE)
        if len(word) > 3
    ]
    for index, clause in enumerate(clauses):
        text = clause.get("text", "").lower()
        if any(keyword in text for keyword in keywords):
            return AnswerResult(
                answer=(
                    f"[Local fallback] Clause {index} may be relevant: "
                    f"{clause.get('text', '')[:200]}"
                ),
                source_clause_indices=[index],
                confidence="low",
            )

    return AnswerResult(
        answer=(
            "[Local fallback] No matching clause found. Set OPENAI_API_KEY "
            "for full agent capability."
        ),
        source_clause_indices=[],
        confidence="low",
    )


def _local_risk_flags(clauses: list[dict]) -> list[RiskFlag]:
    risk_keywords = {
        "indemnif": ("indemnity", "high"),
        "auto-renew": ("auto-renewal", "medium"),
        "automatically renew": ("auto-renewal", "medium"),
        "liquidated damages": ("penalty", "high"),
        "waive": ("liability-waiver", "medium"),
        "arbitration": ("arbitration", "medium"),
        "irrevocable": ("irrevocable-grant", "high"),
        "personal data": ("data-sharing", "medium"),
        "termination for convenience": ("termination", "medium"),
    }

    flags = []
    for index, clause in enumerate(clauses):
        text = clause.get("text", "").lower()
        for keyword, (risk_type, severity) in risk_keywords.items():
            if keyword in text:
                flags.append(
                    RiskFlag(
                        clause_index=index,
                        clause_preview=clause.get("text", "")[:120],
                        risk_type=risk_type,
                        severity=severity,
                        reason=(
                            f"[Local] Clause contains '{keyword}' - "
                            "review recommended."
                        ),
                    )
                )
                break
    return flags


def query_agent(question: str, clauses: list[dict]) -> AnswerResult:
    if not clauses:
        return AnswerResult(
            answer="No clauses have been extracted yet.",
            source_clause_indices=[],
            confidence="low",
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not set - using local fallback.")
        return _local_answer(question, clauses)

    clause_block = _build_clause_list(clauses)
    user_message = f"Clauses:\n{clause_block}\n\nQuestion: {question}"

    try:
        raw = _call_openai(_ANSWER_SYSTEM, user_message)
        data = _parse_json(
            raw,
            {"answer": raw, "source_clause_indices": [], "confidence": "low"},
        )
        return AnswerResult(
            answer=data.get("answer", raw),
            source_clause_indices=[
                int(index) for index in data.get("source_clause_indices", [])
            ],
            confidence=data.get("confidence", "medium"),
        )
    except Exception as exc:
        logger.error("OpenAI query_agent error: %s", exc)
        return AnswerResult(
            answer=f"Agent error: {exc}. Try again or check your API key.",
            source_clause_indices=[],
            confidence="low",
        )


def flag_risky_clauses(clauses: list[dict]) -> list[RiskFlag]:
    if not clauses:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _local_risk_flags(clauses)

    clause_block = _build_clause_list(clauses)

    try:
        raw = _call_openai(_RISK_SYSTEM, f"Clauses:\n{clause_block}")
        data = _parse_json(raw, [])
        flags = []
        for item in data:
            index = int(item.get("clause_index", -1))
            if 0 <= index < len(clauses):
                flags.append(
                    RiskFlag(
                        clause_index=index,
                        clause_preview=clauses[index].get("text", "")[:120],
                        risk_type=item.get("risk_type", "unknown"),
                        severity=item.get("severity", "medium"),
                        reason=item.get("reason", ""),
                    )
                )
        return flags
    except Exception as exc:
        logger.error("OpenAI flag_risky_clauses error: %s", exc)
        return _local_risk_flags(clauses)
