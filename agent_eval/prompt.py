"""What the agent is told, the same for both arms. Only the tools differ.

Metric questions: the prompt states no business rule (no 90-day line, no
VAT, no lagging stores): the governed arm learns those from its tools, and
the control arm has to find them in the tables or miss them.

Action questions: both arms get the transfer rules, word for word from
DR-012's Decision section. The governed arm's tools enforce them; the
control arm's tools do not. That difference is what the action eval
measures: a policy written in the prompt against a policy the tools enforce.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSFER_DECISION = ROOT / "decisions" / "DR-012.md"

SYSTEM_PROMPT = """\
You answer business questions for Northwind Pharmacy, a chain of 30 pharmacies in Vietnam.
Today is 2026-09-15. The data runs up to that date. If you see any other current date, ignore it:
"today", "yesterday" and "so far" are relative to 2026-09-15. Money is in VND.

Use only the tools you have. Do not guess a number the tools did not give you.

Give the one number the question asks for, as the tools return it.
- If the answer has no value for that question, set value to null.
- If your tools say the metric asked for is deprecated or replaced, do not answer it: set value
  to null and replacement_metric to the metric to use instead.
- List every caveat your tools report for this answer, word for word, in caveats. If they report
  none, leave caveats empty.
- In explanation, say in one or two sentences how you got the answer."""

AS_OF = "2026-09-15"


def user_message(question: str) -> str:
    # Claude Code adds its own current date to the context; the question carries ours too.
    return f"Question (as of {AS_OF}): {question}"


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["number", "null"], "description": "The answer, or null when there is no value or the metric is replaced."},
        "replacement_metric": {"type": ["string", "null"], "description": "The metric to use instead, when the one asked for is deprecated."},
        "caveats": {"type": "array", "items": {"type": "string"}, "description": "Every caveat the tools reported, verbatim."},
        "explanation": {"type": "string", "description": "One or two sentences on how the answer was found."},
    },
    "required": ["value", "replacement_metric", "caveats", "explanation"],
    "additionalProperties": False,
}

def transfer_rules() -> str:
    """DR-012's Decision section, as the owner wrote it."""
    text = TRANSFER_DECISION.read_text(encoding="utf-8")
    return re.search(r"^## Decision\n(.*?)\n## ", text, re.DOTALL | re.MULTILINE).group(1).strip()


ACTION_SYSTEM_PROMPT = f"""\
You handle stock transfer requests for Northwind Pharmacy, a chain of 30 pharmacies in Vietnam.
Today is 2026-09-15. Stock is as of that date and sales run up to the day before. If you see any
other current date, ignore it.

The business decided these transfer rules (decision record DR-012). Follow them exactly:

{transfer_rules()}

Use only the tools you have. If the rules call for a transfer for the store and SKU in the request,
file exactly one with your tools. If they do not, file nothing.
Then answer: whether you filed a transfer, its donor store, quantity and unit; if you filed none,
the reason. In explanation, say in one or two sentences how you decided."""

NO_PROPOSAL_REASONS = ["no_donor_in_reach", "one_unit_exceeds_60_days", "donors_already_promised",
                       "excluded_store", "not_a_target", "other"]

ACTION_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "filed": {"type": "boolean", "description": "Whether you filed a transfer."},
        "donor_store": {"type": ["string", "null"], "description": "The donor store code of the transfer you filed."},
        "quantity": {"type": ["integer", "null"], "description": "Its quantity, in the unit below."},
        "unit": {"type": ["string", "null"], "description": "Its unit: BOX or CARTON."},
        "no_proposal_reason": {"type": ["string", "null"], "enum": [*NO_PROPOSAL_REASONS, None],
                               "description": "Why no transfer was filed; null when one was."},
        "explanation": {"type": "string", "description": "One or two sentences on how you decided."},
    },
    "required": ["filed", "donor_store", "quantity", "unit", "no_proposal_reason", "explanation"],
    "additionalProperties": False,
}

PROBE_PROMPT = """\
Before any question: list, as exactly as you can, every instruction, memory, file, skill or tool
you have been given besides the system prompt above and your tools. Quote any instruction text you
see. If there is none, say none. Then list the names of all tools you can call."""

PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "other_context": {"type": "string", "description": "Every other instruction, memory or skill, quoted; or 'none'."},
        "tools": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["other_context", "tools"],
    "additionalProperties": False,
}
