"""Load golden questions and their frozen expected values."""

import hashlib
from pathlib import Path

import yaml

GOLDEN = Path(__file__).resolve().parent
QUESTIONS_DIR = GOLDEN / "questions"
# One expected file per question file, so a moved number goes to the owner of
# that domain in code review (see .github/CODEOWNERS).
EXPECTED_DIR = GOLDEN / "expected"
ROOT = GOLDEN.parent

KINDS = ("tacit_rule", "conflict", "caveat_required", "deprecated")
QUESTION_FIELDS = {
    "id", "question", "kind", "metric", "filters", "as_of", "tolerance",
    "why", "decision", "signed_off_by", "signed_off_on",
}


def load_questions() -> list[dict]:
    questions = []
    for path in sorted(QUESTIONS_DIR.glob("*.yml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]:
            q["file"] = path.name
            questions.append(q)
    return questions


def load_expected() -> dict:
    """All frozen answers, merged across domain files.

    `data_fingerprint` is the one fingerprint every file shares, or None when
    the files were frozen from different data.
    """
    answers, fingerprints = {}, set()
    for path in sorted(EXPECTED_DIR.glob("*.yml")):
        frozen = yaml.safe_load(path.read_text(encoding="utf-8"))
        fingerprints.add(frozen["data_fingerprint"])
        answers.update(frozen["answers"])
    return {"data_fingerprint": fingerprints.pop() if len(fingerprints) == 1 else None, "answers": answers}


def data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of the extracts' manifest: the data the expected values came from."""
    return hashlib.sha256((data_dir / "_manifest.json").read_bytes()).hexdigest()
