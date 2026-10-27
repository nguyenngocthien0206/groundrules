"""What the agent is told, the same for both arms. Only the tools differ.

The prompt states no business rule (no 90-day line, no VAT, no lagging
stores): the governed arm learns those from its tools, and the control arm
has to find them in the tables or miss them. That difference is what the
eval measures.
"""

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
