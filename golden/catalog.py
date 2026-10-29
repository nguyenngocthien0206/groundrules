"""Load golden questions and their frozen expected values, for metrics and for actions."""

import hashlib
from pathlib import Path

import yaml

GOLDEN = Path(__file__).resolve().parent
QUESTIONS_DIR = GOLDEN / "questions"
# One expected file per question file, so a moved number goes to the owner of
# that domain in code review (see .github/CODEOWNERS).
EXPECTED_DIR = GOLDEN / "expected"
ROOT = GOLDEN.parent

# Questions about actions (v0.3) live apart: they expect a proposal, not a number.
ACTION_QUESTIONS_DIR = GOLDEN / "actions" / "questions"
ACTION_EXPECTED_DIR = GOLDEN / "actions" / "expected"
ACTION_KINDS = ("proposal", "no_proposal")
ACTION_REASONS = ("no_donor_in_reach", "one_unit_exceeds_60_days", "donors_already_promised", "excluded_store", "not_a_target")

KINDS = ("tacit_rule", "conflict", "caveat_required", "deprecated")
QUESTION_FIELDS = {
    "id", "question", "kind", "metric", "filters", "as_of", "tolerance",
    "why", "decision", "signed_off_by", "signed_off_on",
}


def load_questions(questions_dir: Path = QUESTIONS_DIR) -> list[dict]:
    questions = []
    for path in sorted(questions_dir.glob("*.yml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]:
            q["file"] = path.name
            questions.append(q)
    return questions


def load_action_questions() -> list[dict]:
    return load_questions(ACTION_QUESTIONS_DIR)


def load_action_expected() -> dict:
    return load_expected(ACTION_EXPECTED_DIR)


def load_expected(expected_dir: Path = EXPECTED_DIR) -> dict:
    """All frozen answers, merged across domain files.

    `data_fingerprint` is the one fingerprint every file shares, or None when
    the files were frozen from different data.
    """
    answers, fingerprints = {}, set()
    for path in sorted(expected_dir.glob("*.yml")):
        frozen = yaml.safe_load(path.read_text(encoding="utf-8"))
        fingerprints.add(frozen["data_fingerprint"])
        answers.update(frozen["answers"])
    return {"data_fingerprint": fingerprints.pop() if len(fingerprints) == 1 else None, "answers": answers}


def data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of the extracts' manifest: the data the expected values came from."""
    return hashlib.sha256((data_dir / "_manifest.json").read_bytes()).hexdigest()
