#!/usr/bin/env python3
"""Fail-closed verifier for the complete repository candidate."""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import pypdf
from pypdf import PdfReader
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    StreamObject,
)

from check_manifest import (
    EXPECTED_DIRECTORIES,
    PDF_PATH,
    ROOT,
    check_manifest,
    inspect_tree,
    native_path,
)
from git_boundary import (
    ensure_git_repository_safety,
    git_output,
    run_git,
)
from runtime_boundary import trusted_git_executable


RELEASE_NAME = "RELEASE_SHA256.txt"
ALLOWED_PATHS = {
    ".github/workflows/verify.yml",
    ".gitattributes",
    ".gitignore",
    "ACCESSIBILITY.md",
    "AI_USE.md",
    "CITATION.cff",
    "LICENSE",
    "LICENSE_SCOPE.md",
    "MANIFEST_SHA256.txt",
    "README.md",
    "README_REVIEWER.md",
    "REPRODUCE.md",
    RELEASE_NAME,
    "THIRD_PARTY_NOTICES.md",
    "companion/affine_hjelmslev_radon_smith.py",
    "docs/PUBLIC_CLAIM_BOUNDARY.md",
    "docs/REPRODUCIBILITY_BOUNDARY.md",
    "docs/SOURCE_AND_ATTRIBUTION.md",
    "docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md",
    "paper/latexmkrc",
    "paper/main.tex",
    "paper/references.bib",
    PDF_PATH,
    "requirements.lock",
    "requirements.txt",
    "scripts/check_manifest.py",
    "scripts/check_external_review_evidence.py",
    "scripts/check_release.py",
    "scripts/git_boundary.py",
    "scripts/runtime_bootstrap.py",
    "scripts/runtime_boundary.py",
    "scripts/verify.py",
    "tests/test_affine_hjelmslev_radon_smith.py",
    "tests/test_release_assurance.py",
}
RELEASE_PATHS = {"MANIFEST_SHA256.txt", PDF_PATH}
TEXT_SUFFIXES = {
    "",
    ".bib",
    ".cff",
    ".html",
    ".lock",
    ".md",
    ".py",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_STATIC_FOLD_CHARS = 1024 * 1024
EXPECTED_BIBLIOGRAPHY_SHA256 = (
    "09ABE305CB625B03581EEAB2F0FE73FB7C9CA9F7C7949D76060ACE540CEDB13C"
)
EXPECTED_CITATION_KEYS = {
    "BLR23",
    "CSX06",
    "DVI26",
    "HVM89",
    "ILM",
    "KOH09",
    "LAN17",
    "LIP93",
    "LT25",
    "LV14",
    "LW03",
    "MOL12",
    "MS15",
    "SIN14",
    "STK-TOR",
    "WK04",
}
GENERIC_HYGIENE_PATTERNS = (
    (
        "absolute Windows workspace path",
        re.compile(r"(?i)(?<![A-Z0-9_])[A-Z]:[\\/](?=[^\\/\r\n])"),
    ),
    (
        "hidden workspace path",
        re.compile(
            r"(?i)(?:^|[\\/])\.(?!github(?:[\\/]|$))"
            r"[a-z0-9][a-z0-9_-]*(?=[\\/])"
        ),
    ),
    (
        "internal project code",
        re.compile(r"(?<![A-Za-z0-9_])P[0-9]{2,4}(?![A-Za-z0-9_])"),
    ),
    (
        "internal lifecycle identifier",
        re.compile(
            r"\b(?:PO[0-9]{1,2}(?:-[A-Z0-9]+)*|"
            r"P[0-9]{1,4}-(?:PO|F|C|G|SECTION|STATEMENT|CLAIM|TABLE|FIGURE)"
            r"[A-Z0-9_-]*|PROJECT-[0-9]{1,4}-[A-Z0-9_-]+)\b"
        ),
    ),
    (
        "internal project-prefixed filename",
        re.compile(r"(?i)\bp[0-9]{2,4}_[a-z0-9_]+\.(?:py|bib|tex)\b"),
    ),
)
ASSURANCE_PYTHON_PATHS = {
    "scripts/check_external_review_evidence.py",
    "scripts/check_manifest.py",
    "scripts/check_release.py",
    "scripts/git_boundary.py",
    "scripts/runtime_bootstrap.py",
    "scripts/runtime_boundary.py",
    "scripts/verify.py",
}
FORBIDDEN_DYNAMIC_ATTRIBUTE_CALLS = {
    "a85decode",
    "b64decode",
    "b85decode",
    "decode",
    "decodebytes",
    "fromhex",
    "standard_b64decode",
    "urlsafe_b64decode",
}
FORBIDDEN_DYNAMIC_NAME_CALLS = {"chr", "compile", "eval", "exec"}
PDF_WHITESPACE = frozenset(b"\x00\x09\x0A\x0C\x0D\x20")
RAW_PDF_FORBIDDEN_MARKERS = {
    b"/AA",
    b"/EmbeddedFile",
    b"/EmbeddedFiles",
    b"/Filespec",
    b"/JavaScript",
    b"/Launch",
    b"/RichMedia",
    b"/XFA",
}
PRINTABLE_PDF_RUN = re.compile(rb"[\x20-\x7E]{8,}")
FORBIDDEN_PDF_KEYS = {
    "/AA",
    "/EmbeddedFiles",
    "/EF",
    "/JavaScript",
    "/JS",
    "/RichMediaContent",
    "/RichMediaSettings",
    "/XFA",
}
FORBIDDEN_PDF_ACTIONS = {
    "/GoTo3DView",
    "/GoToE",
    "/GoToR",
    "/Hide",
    "/ImportData",
    "/JavaScript",
    "/Launch",
    "/Movie",
    "/Named",
    "/Rendition",
    "/ResetForm",
    "/Sound",
    "/SubmitForm",
    "/Thread",
    "/Trans",
}
PUBLIC_REPOSITORY_URL = (
    "https://github.com/aconsciousfractal/"
    "FCIG-Depth-Two-Smith-Profiles-and-Carry-Geometry-for-"
    "Affine-Hjelmslev-Radon-Incidence"
)
PUBLIC_AUTHOR_NAME = "Oleksiy Babanskyy"
VISIBLE_GOVERNANCE_CODE = re.compile(
    r"\b(?:[A-Z]-[A-Z][0-9]+|FIG-[0-9]+|TAB-[0-9]+|P[0-9]{2,4})\b"
)
MALFORMED_TEX_PATTERNS = (
    ("bare TeX spacing command", re.compile(r"(?<!\\)\b(?:quad|qquad)\b")),
    ("malformed TeX superscript", re.compile(r"\^\{,")),
)
PINNED_ACTION_REFS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
}


def _sha256(path: Path) -> str:
    with native_path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def _parse_release(root: Path = ROOT) -> list[tuple[str, str]]:
    release = root / RELEASE_NAME
    if not native_path(release).is_file():
        raise AssertionError("release manifest is missing")
    rows: list[tuple[str, str]] = []
    for line_number, raw in enumerate(
        native_path(release).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        fields = raw.split(maxsplit=1)
        if len(fields) != 2:
            raise AssertionError(f"malformed release line {line_number}")
        digest, relative = fields
        if len(digest) != 64 or any(ch not in "0123456789ABCDEF" for ch in digest):
            raise AssertionError(f"invalid release SHA-256 on line {line_number}")
        rows.append((digest, relative))
    if {path for _, path in rows} != RELEASE_PATHS or len(rows) != 2:
        raise AssertionError("release manifest must pin exactly the source manifest and PDF")
    if [path for _, path in rows] != sorted(path for _, path in rows):
        raise AssertionError("release manifest paths are not sorted")
    return rows


def _check_closed_tree(root: Path = ROOT) -> dict[str, set[str]]:
    tree = inspect_tree(root)
    observed = tree["files"]
    if observed != ALLOWED_PATHS:
        raise AssertionError(
            f"repository path drift: missing={sorted(ALLOWED_PATHS - observed)}, "
            f"extra={sorted(observed - ALLOWED_PATHS)}"
        )
    if tree["directories"] != EXPECTED_DIRECTORIES:
        raise AssertionError("repository directory contract drift")
    for relative in sorted(observed):
        path = root / Path(*PurePosixPath(relative).parts)
        if native_path(path).stat().st_size > MAX_FILE_BYTES:
            raise AssertionError(f"oversize artifact: {relative}")
    return tree


def _scan_hygiene_text(text: str, relative: str) -> None:
    for label, pattern in GENERIC_HYGIENE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} in {relative}")


def _fold_static_text(node: ast.AST) -> str | None:
    """Fold only statically decidable Python text, without executing code."""

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            if len(node.value) > MAX_STATIC_FOLD_CHARS:
                raise AssertionError("static Python text exceeds the fold bound")
            return node.value
        if isinstance(node.value, bytes):
            try:
                text = str(node.value, "ascii")
            except UnicodeDecodeError:
                return None
            if len(text) > MAX_STATIC_FOLD_CHARS:
                raise AssertionError("static Python bytes exceed the fold bound")
            return text
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_static_text(node.left)
        right = _fold_static_text(node.right)
        if left is not None and right is not None:
            if len(left) + len(right) > MAX_STATIC_FOLD_CHARS:
                raise AssertionError("static Python concatenation exceeds the fold bound")
            return left + right
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
            left = _fold_static_text(node.left)
            if left is not None and 0 <= node.right.value <= 4096:
                if len(left) * node.right.value > MAX_STATIC_FOLD_CHARS:
                    raise AssertionError("static Python repetition exceeds the fold bound")
                return left * node.right.value
        if isinstance(node.left, ast.Constant) and isinstance(node.left.value, int):
            right = _fold_static_text(node.right)
            if right is not None and 0 <= node.left.value <= 4096:
                if len(right) * node.left.value > MAX_STATIC_FOLD_CHARS:
                    raise AssertionError("static Python repetition exceeds the fold bound")
                return node.left.value * right
        return None
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        total_length = 0
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                piece = value.value
            elif (
                isinstance(value, ast.FormattedValue)
                and isinstance(value.value, ast.Constant)
                and value.format_spec is None
            ):
                scalar = value.value.value
                if not isinstance(scalar, (str, bytes, int, float, complex, bool)):
                    return None
                if value.conversion in {-1, ord("s")}:
                    piece = str(scalar)
                elif value.conversion == ord("r"):
                    piece = repr(scalar)
                elif value.conversion == ord("a"):
                    piece = ascii(scalar)
                else:
                    return None
            else:
                return None
            total_length += len(piece)
            if total_length > MAX_STATIC_FOLD_CHARS:
                raise AssertionError("static Python formatted text exceeds the fold bound")
            pieces.append(piece)
        return "".join(pieces)
    return None


def _scan_python_source(
    text: str, relative: str, *, assurance_language: bool,
) -> None:
    """Scan supported static literals and the bounded assurance language."""

    try:
        syntax = ast.parse(text, filename=relative)
    except SyntaxError as error:
        raise AssertionError(f"invalid Python syntax in {relative}") from error
    for node in ast.walk(syntax):
        folded = _fold_static_text(node)
        if folded is not None:
            _scan_hygiene_text(folded, f"{relative}:static-constant")
        if assurance_language and isinstance(node, ast.Call):
            call_name: str | None = None
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
                forbidden = FORBIDDEN_DYNAMIC_NAME_CALLS
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
                forbidden = FORBIDDEN_DYNAMIC_ATTRIBUTE_CALLS
            else:
                forbidden = set()
            if call_name in forbidden:
                raise AssertionError(
                    f"forbidden dynamic reconstruction primitive "
                    f"{call_name} in assurance file {relative}"
                )


def _check_text_hygiene(root: Path = ROOT) -> None:
    for relative in sorted(ALLOWED_PATHS):
        path = root / Path(*PurePosixPath(relative).parts)
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            "LICENSE",
            ".gitignore",
            ".gitattributes",
        }:
            continue
        text = native_path(path).read_text(encoding="utf-8")
        _scan_hygiene_text(text, relative)
        if path.suffix.lower() == ".py":
            _scan_python_source(
                text,
                relative,
                assurance_language=relative in ASSURANCE_PYTHON_PATHS,
            )


def _check_tex_source(root: Path = ROOT) -> None:
    manuscript = native_path(root / "paper" / "main.tex").read_text(
        encoding="utf-8"
    )
    for label, pattern in MALFORMED_TEX_PATTERNS:
        match = pattern.search(manuscript)
        if match:
            line = manuscript.count("\n", 0, match.start()) + 1
            raise AssertionError(f"{label} on manuscript line {line}")


def _citation_keys(manuscript: str) -> set[str]:
    keys: set[str] = set()
    pattern = re.compile(r"\\cite(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
    for match in pattern.finditer(manuscript):
        keys.update(key.strip() for key in match.group(1).split(","))
    return keys


def _check_scientific_locks(root: Path = ROOT) -> None:
    bibliography_path = root / "paper" / "references.bib"
    if _sha256(bibliography_path) != EXPECTED_BIBLIOGRAPHY_SHA256:
        raise AssertionError("exact cited-only bibliography lock drift")
    bibliography = native_path(bibliography_path).read_text(encoding="utf-8")
    bibliography_keys = set(
        re.findall(r"(?m)^@[A-Za-z]+\{([^,]+),", bibliography)
    )
    if bibliography_keys != EXPECTED_CITATION_KEYS:
        raise AssertionError("bibliography key census drift")
    if (
        "Bajalan, Maryam and Landjev, Ivan and Rousseva, Assia"
        not in bibliography
    ):
        raise AssertionError("BLR23 author metadata drift")

    manuscript = native_path(root / "paper" / "main.tex").read_text(
        encoding="utf-8"
    )
    if "\\author{Oleksiy Babanskyy}" not in manuscript:
        raise AssertionError("author metadata drift")
    public_template_locks = (
        "\\documentclass[12pt,a4paper]{article}",
        "\\date{}",
        "\\pagestyle{plain}",
        "\\pdfextension catalog {/Lang (en-US)}",
        "\\noindent\\textbf{Keywords:}",
        "\\noindent\\textbf{MSC 2020:}",
        PUBLIC_REPOSITORY_URL,
    )
    for lock in public_template_locks:
        if lock not in manuscript:
            raise AssertionError(f"public manuscript template drift: {lock}")
    ai_disclosure = native_path(root / "AI_USE.md").read_text(encoding="utf-8")
    normalized_manuscript = " ".join(manuscript.split())
    normalized_ai_disclosure = " ".join(ai_disclosure.split())
    ai_disclosure_locks = (
        "OpenAI Codex",
        "GPT-5.6 Sol",
        "generated the central mathematical development",
        "takes responsibility for the final content",
        "not human peer review or independent expert verification",
    )
    for lock in ai_disclosure_locks:
        if (
            lock not in normalized_manuscript
            or lock not in normalized_ai_disclosure
        ):
            raise AssertionError(f"AI-use disclosure drift: {lock}")
    if "The theorem includes $p=5$" not in normalized_manuscript:
        raise AssertionError("p=5 theorem/computation boundary drift")
    for obsolete in (
        "no result at\n$(p,n)=(5,2)$",
        "no $(5,2)$ result",
    ):
        if obsolete in normalized_manuscript:
            raise AssertionError("obsolete p=5 exclusion in manuscript")
    if "\\documentclass{amsart}" in manuscript or "\\stmtid" in manuscript:
        raise AssertionError("private or running-head manuscript template")
    if re.search(r"(?:FIG|TAB)-[0-9]+", manuscript):
        raise AssertionError("visible figure/table lifecycle code in manuscript")
    if "\\addbibresource{references.bib}" not in manuscript:
        raise AssertionError("bibliography filename drift")
    if (
        "<8F1E23165A4716CCB61682522345BBF9>"
        not in manuscript
    ):
        raise AssertionError("deterministic PDF trailer identity drift")
    if _citation_keys(manuscript) != bibliography_keys:
        raise AssertionError("cited-only bibliography relation drift")
    if "\\mbox{\\cite{HVM89,KOH09}}" not in manuscript:
        raise AssertionError("nonbreaking two-source citation drift")

    citation = native_path(root / "CITATION.cff").read_text(encoding="utf-8")
    citation_locks = (
        'title: "Affine Hjelmslev--Radon Smith Exact-Arithmetic Companion"',
        "type: software",
        f'repository-code: "{PUBLIC_REPOSITORY_URL}"',
        "preferred-citation:\n  type: article",
    )
    for lock in citation_locks:
        if lock not in citation:
            raise AssertionError(f"citation metadata boundary drift: {lock}")

    license_scope = native_path(root / "LICENSE_SCOPE.md").read_text(
        encoding="utf-8"
    )
    if "Copyright in the manuscript is retained" not in license_scope:
        raise AssertionError("retained manuscript copyright is not explicit")
    if "`paper/*.pdf` | **not MIT**" not in license_scope:
        raise AssertionError("paper PDF license scope drift")

    lockfile = native_path(root / "requirements.lock").read_text(encoding="utf-8")
    required_packages = {
        "colorama==0.4.6",
        "iniconfig==2.3.0",
        "mpmath==1.3.0",
        "packaging==26.2",
        "pluggy==1.6.0",
        "Pygments==2.20.0",
        "pypdf==6.14.2",
        "pytest==9.1.1",
        "sympy==1.14.0",
    }
    observed_packages = {
        line.split(maxsplit=1)[0]
        for line in lockfile.splitlines()
        if line and not line.startswith(("#", " "))
    }
    if observed_packages != required_packages:
        raise AssertionError("hash-locked dependency census drift")
    hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})", lockfile)
    if len(hashes) != len(required_packages) or len(set(hashes)) != len(hashes):
        raise AssertionError("dependency hash lock drift")

    workflow = native_path(root / ".github" / "workflows" / "verify.yml").read_text(
        encoding="utf-8"
    )
    workflow_locks = (
        'python-version: ["3.12", "3.13", "3.14"]',
        "--require-hashes -r requirements.lock",
        'PYTHON_ABSOLUTE=$(python -I -S -c',
        'GIT_ABSOLUTE=$(command -v git)',
        '"$PYTHON_ABSOLUTE" -I -S -B -O scripts/runtime_bootstrap.py',
        "--git-executable \"$GIT_ABSOLUTE\" --module pytest",
        "tests/test_release_assurance.py",
        "--target scripts/check_release.py",
        "Optimized pytest compatibility only; not an assurance layer",
        "Build twice and compare bytes and semantics",
        "git diff --exit-code -- .",
    )
    for lock in workflow_locks:
        if lock not in workflow:
            raise AssertionError(f"public CI contract drift: {lock}")
    action_rows = re.findall(
        r"(?m)^\s*-\s+uses:\s+([^@\s]+)@([^\s#]+)", workflow
    )
    expected_rows = [
        (name, revision)
        for name, revision in PINNED_ACTION_REFS.items()
        for _ in range(2)
    ]
    if sorted(action_rows) != sorted(expected_rows):
        raise AssertionError(f"immutable GitHub Action pins drift: {action_rows}")
    if any(not re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in action_rows):
        raise AssertionError("GitHub Actions must use full immutable commit SHAs")

    companion = native_path(
        root / "companion" / "affine_hjelmslev_radon_smith.py"
    ).read_text(encoding="utf-8")
    locks = (
        'HNF_PROPERTY_SEED = b"affine-hjelmslev-radon-hnf-property-v1"',
        "B034902692C686DE339F0C0728AB61EA75E7C8E8090AA7DF34756D02B0CCCAE2",
        "7845D3E42299B2DF7C0FE9E60BB7EA34B987E88E8FBEEE905EDB8DB7A3364A76",
        "302046F44218EEDDC2587A5167643AEF1118E3E06888CBCF60D15AFBDE4BE86D",
    )
    for lock in locks:
        if lock not in companion:
            raise AssertionError(f"companion assurance lock missing: {lock}")


def _resolve_pdf_object(value):
    while isinstance(value, IndirectObject):
        value = value.get_object()
    return value


def _complete_pdf_references(reader: PdfReader) -> list[IndirectObject]:
    identities: set[tuple[int, int]] = set()
    for generation, entries in reader.xref.items():
        for identifier in entries:
            if identifier > 0:
                identities.add((identifier, generation))
    for identifier in reader.xref_objStm:
        if identifier > 0:
            identities.add((identifier, 0))
    size = int(_resolve_pdf_object(reader.trailer.get("/Size")))
    if size <= 1 or any(identifier >= size for identifier, _ in identities):
        raise AssertionError("PDF xref identity lies outside trailer Size")
    return [
        IndirectObject(identifier, generation, reader)
        for identifier, generation in sorted(identities)
    ]


def _walk_complete_pdf_objects(reader: PdfReader):
    references = _complete_pdf_references(reader)
    stack = [reader.trailer, *references]
    seen_indirect: set[tuple[int, int, int]] = set()
    seen_direct: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, IndirectObject):
            key = (id(current.pdf), current.idnum, current.generation)
            if key in seen_indirect:
                continue
            seen_indirect.add(key)
            stack.append(current.get_object())
            continue
        if isinstance(current, (DictionaryObject, ArrayObject)):
            identity = id(current)
            if identity in seen_direct:
                continue
            seen_direct.add(identity)
        yield current
        if isinstance(current, DictionaryObject):
            stack.extend(current.values())
        elif isinstance(current, ArrayObject):
            stack.extend(current)


def _scan_pdf_bytes(payload: bytes, *, label: str) -> None:
    for marker in sorted(RAW_PDF_FORBIDDEN_MARKERS):
        if marker in payload:
            raise AssertionError(
                f"forbidden PDF raw marker in {label}: {str(marker, 'ascii')}"
            )
    for match in PRINTABLE_PDF_RUN.finditer(payload):
        _scan_hygiene_text(str(match.group(0), "ascii"), label)


def _check_terminal_pdf_bytes(payload: bytes) -> None:
    marker = b"%%EOF"
    if payload.count(marker) != 1:
        raise AssertionError("PDF must contain exactly one EOF marker")
    end = payload.index(marker) + len(marker)
    if any(value not in PDF_WHITESPACE for value in payload[end:]):
        raise AssertionError("PDF contains non-whitespace bytes after terminal EOF")
    _scan_pdf_bytes(payload, label="complete raw PDF")


def _safe_external_uri(value: object) -> bool:
    uri = str(_resolve_pdf_object(value))
    parsed = urlsplit(uri)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def inspect_pdf(path: Path) -> dict[str, object]:
    if pypdf.__version__ != "6.14.2":
        raise AssertionError(f"unsupported pypdf version: {pypdf.__version__}")
    payload = native_path(path).read_bytes()
    _check_terminal_pdf_bytes(payload)
    reader = PdfReader(str(native_path(path)), strict=True)
    if reader.is_encrypted:
        raise AssertionError("encrypted PDF is not allowed")
    catalog = _resolve_pdf_object(reader.trailer["/Root"])
    if not isinstance(catalog, DictionaryObject):
        raise AssertionError("malformed PDF catalog")
    if "/AcroForm" in catalog:
        raise AssertionError("PDF forms are not allowed")
    if "/Collection" in catalog:
        raise AssertionError("PDF collection is not allowed")
    language = str(_resolve_pdf_object(catalog.get("/Lang")))
    if language != "en-US":
        raise AssertionError(f"PDF language drift: {language}")

    open_action = "NONE"
    if "/OpenAction" in catalog:
        action = _resolve_pdf_object(catalog["/OpenAction"])
        if isinstance(action, ArrayObject):
            if len(action) < 2 or not str(_resolve_pdf_object(action[1])).startswith(
                "/Fit"
            ):
                raise AssertionError("unsafe PDF OpenAction destination")
            open_action = "INTERNAL_DESTINATION"
        elif isinstance(action, DictionaryObject):
            if str(_resolve_pdf_object(action.get("/S"))) != "/GoTo":
                raise AssertionError("unsafe PDF OpenAction dictionary")
            open_action = "INTERNAL_GOTO"
        else:
            raise AssertionError("unsafe PDF OpenAction type")

    uri_actions = 0
    goto_actions = 0
    references = _complete_pdf_references(reader)
    for value in _walk_complete_pdf_objects(reader):
        if isinstance(value, StreamObject):
            try:
                stream_payload = value.get_data()
            except Exception as error:
                raise AssertionError("cannot decode a PDF stream") from error
            _scan_pdf_bytes(stream_payload, label="decoded PDF stream")
        elif isinstance(value, bytes):
            _scan_pdf_bytes(value, label="PDF byte string")
        elif isinstance(value, str) and value:
            _scan_hygiene_text(value, "PDF text string")
        if not isinstance(value, DictionaryObject):
            continue
        keys = {str(key) for key in value.keys()}
        forbidden_keys = keys & FORBIDDEN_PDF_KEYS
        if forbidden_keys:
            raise AssertionError(
                f"forbidden PDF key: {sorted(forbidden_keys)[0]}"
            )
        object_type = str(_resolve_pdf_object(value.get("/Type")))
        subtype = str(_resolve_pdf_object(value.get("/Subtype")))
        if object_type in {"/EmbeddedFile", "/Filespec"}:
            raise AssertionError(f"forbidden PDF object type: {object_type}")
        if subtype in {"/FileAttachment", "/RichMedia"}:
            raise AssertionError(f"forbidden PDF annotation subtype: {subtype}")
        if "/FS" in keys:
            raise AssertionError("PDF file specification is not allowed")

        action_type = str(_resolve_pdf_object(value.get("/S")))
        if action_type in FORBIDDEN_PDF_ACTIONS:
            raise AssertionError(f"forbidden PDF action: {action_type}")
        if action_type == "/URI" or "/URI" in keys:
            if "/URI" not in value or not _safe_external_uri(value["/URI"]):
                raise AssertionError("local or malformed PDF URI")
            uri_actions += 1
        elif action_type == "/GoTo":
            goto_actions += 1

    metadata = reader.metadata
    if metadata is None:
        raise AssertionError("PDF metadata is missing")
    metadata_values = {
        "Title": metadata.title,
        "Author": metadata.author,
        "Subject": metadata.subject,
        "Keywords": metadata.get("/Keywords"),
    }
    for key, value in metadata_values.items():
        if not isinstance(value, str) or not value.strip():
            raise AssertionError(f"PDF metadata field missing: {key}")
        if "\ufffd" in value or not value.isascii():
            raise AssertionError(f"PDF metadata is not ASCII-safe: {key}")

    page_text: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        box = tuple(float(value) for value in page.mediabox)
        width = box[2] - box[0]
        height = box[3] - box[1]
        if abs(width - 595.276) > 1.0 or abs(height - 841.89) > 1.0:
            raise AssertionError(
                f"non-A4 PDF page {page_number}: {width:.3f}x{height:.3f}"
            )
        page_text.append(page.extract_text() or "")

    full_text = "\n".join(page_text)
    match = VISIBLE_GOVERNANCE_CODE.search(full_text)
    if match:
        raise AssertionError(f"visible governance code in PDF: {match.group(0)}")
    author_pages = [
        page_number
        for page_number, text in enumerate(page_text, start=1)
        if re.search(re.escape(PUBLIC_AUTHOR_NAME), text, flags=re.IGNORECASE)
    ]
    if author_pages != [1]:
        raise AssertionError(f"author must appear only on PDF page 1: {author_pages}")
    for token in (
        "Keywords:",
        "MSC 2020:",
        "github.com/aconsciousfractal",
        "AI-use disclosure and author responsibility",
        "GPT-5.6 Sol",
    ):
        if token not in full_text:
            raise AssertionError(f"visible PDF front matter missing: {token}")
    if "24 August 2026" in full_text:
        raise AssertionError("obsolete visible manuscript date")

    return {
        "pages": len(reader.pages),
        "eof_markers": 1,
        "xref_objects": len(references),
        "object_stream_members": len(reader.xref_objStm),
        "page_size": "A4",
        "language": language,
        "author_pages": author_pages,
        "uri_actions": uri_actions,
        "goto_actions": goto_actions,
        "open_action": open_action,
        "metadata": metadata_values,
    }


def _run_git(root: Path, *arguments: str):
    return run_git(list(arguments), root=root)


def _git_output(root: Path, *arguments: str) -> str:
    return git_output(root, *arguments)


def inspect_git_history(root: Path = ROOT) -> dict[str, object]:
    """Bind content verification to a clean checkout of the current HEAD.

    The content check is independent of branching policy: ordinary corrective
    descendants, merges, tags, remotes and detached CI checkouts are valid.
    Local mechanisms that can silently rewrite object lookup remain forbidden.
    """

    ensure_git_repository_safety(root=root)
    top_level = _git_output(root, "rev-parse", "--show-toplevel")
    if Path(top_level).resolve() != root.resolve():
        raise AssertionError("repository root is not the Git toplevel")

    head = _git_output(root, "rev-parse", "--verify", "HEAD^{commit}")
    tree = _git_output(root, "rev-parse", "HEAD^{tree}")
    if _git_output(root, "replace", "-l"):
        raise AssertionError("Git replace refs are not allowed")

    for administrative_path in ("info/grafts", "objects/info/alternates"):
        relative = _git_output(root, "rev-parse", "--git-path", administrative_path)
        path = Path(relative)
        if not path.is_absolute():
            path = root / path
        if path.exists() and path.stat().st_size:
            raise AssertionError(f"Git administrative override: {administrative_path}")

    tracked = {
        PurePosixPath(row).as_posix()
        for row in _git_output(root, "ls-files").splitlines()
        if row
    }
    if tracked != ALLOWED_PATHS:
        raise AssertionError(
            "tracked path census drift: "
            f"missing={sorted(ALLOWED_PATHS - tracked)}, "
            f"extra={sorted(tracked - ALLOWED_PATHS)}"
        )

    status = _git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise AssertionError(f"Git worktree is not clean: {status}")

    fsck = _run_git(
        root,
        "fsck",
        "--strict",
        "--connectivity-only",
        "--no-progress",
        "HEAD",
    )
    fsck_text = "\n".join((fsck.stdout, fsck.stderr)).strip()
    if fsck.returncode != 0:
        raise AssertionError(f"Git object connectivity failed: {fsck_text}")

    commit_count = len(
        [row for row in _git_output(root, "rev-list", "HEAD").splitlines() if row]
    )

    return {
        "commit": head,
        "tree": tree,
        "commits": commit_count,
        "tracked_files": len(tracked),
        "shallow": _git_output(root, "rev-parse", "--is-shallow-repository")
        == "true",
        "git_executable_sha256": _sha256(trusted_git_executable()),
    }


def check_release(root: Path = ROOT) -> dict[str, object]:
    tree = _check_closed_tree(root)
    _check_text_hygiene(root)
    _check_tex_source(root)
    _check_scientific_locks(root)
    pdf = inspect_pdf(root / Path(*PurePosixPath(PDF_PATH).parts))
    source = check_manifest(root)
    rows = _parse_release(root)
    for expected, relative in rows:
        path = root / Path(*PurePosixPath(relative).parts)
        if _sha256(path) != expected:
            raise AssertionError(f"release digest mismatch: {relative}")
    git = inspect_git_history(root)
    return {
        "status": "PASS",
        "source_files": source["source_files"],
        "repository_files": len(tree["files"]),
        "repository_directories": len(tree["directories"]),
        "release_files": len(rows),
        "pdf": pdf,
        "git": git,
    }


def main() -> int:
    result = check_release()
    print(
        "RELEASE PASS "
        f"files={result['repository_files']} "
        f"directories={result['repository_directories']} "
        f"release_pins={result['release_files']} "
        f"pdf_pages={result['pdf']['pages']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
