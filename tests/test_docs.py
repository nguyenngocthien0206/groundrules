"""The README, changelog, playbook and adoption guide stay true as the repo changes.

Docs that name files and commands rot without anyone noticing. These checks
fail when a link points nowhere, a `make` target does not exist, or a page
is missing from its folder's index.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("playbook", "adoption")
PAGES = [ROOT / "README.md", ROOT / "CHANGELOG.md"] + sorted(p for folder in FOLDERS for p in (ROOT / folder).glob("*.md"))

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# `make target` in inline code, or a fenced line that starts with make.
MAKE = re.compile(r"(?:`|^)make ([a-z][\w-]*)", re.MULTILINE)
TARGET = re.compile(r"^([a-z][\w-]*):", re.MULTILINE)


def ids(paths):
    return [p.relative_to(ROOT).as_posix() for p in paths]


def test_both_folders_have_pages():
    for folder in FOLDERS:
        assert (ROOT / folder / "README.md").exists()
        assert len(list((ROOT / folder).glob("*.md"))) >= 5, folder


@pytest.mark.parametrize("page", PAGES, ids=ids(PAGES))
def test_relative_links_point_to_files_that_exist(page):
    text = page.read_text(encoding="utf-8")
    for target in LINK.findall(text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue  # web links and anchors
        path = (page.parent / target.split("#", 1)[0]).resolve()
        assert path.exists(), f"{page.relative_to(ROOT).as_posix()} links to {target}, which does not exist"


@pytest.mark.parametrize("page", PAGES, ids=ids(PAGES))
def test_make_targets_named_in_docs_exist(page):
    targets = set(TARGET.findall((ROOT / "Makefile").read_text(encoding="utf-8")))
    for name in MAKE.findall(page.read_text(encoding="utf-8")):
        assert name in targets, f"{page.relative_to(ROOT).as_posix()} mentions `make {name}`, which is not in the Makefile"


@pytest.mark.parametrize("folder", FOLDERS)
def test_every_page_is_in_its_folder_index(folder):
    index = (ROOT / folder / "README.md").read_text(encoding="utf-8")
    for page in (ROOT / folder).glob("*.md"):
        if page.name != "README.md":
            assert f"]({page.name})" in index, f"{folder}/README.md does not list {page.name}"
