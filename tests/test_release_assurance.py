from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
from pypdf import PdfReader

from test_affine_hjelmslev_radon_smith import (
    PDF,
    ROOT,
    _copy_candidate,
    _public_git_environment,
)


SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_release import _scan_python_source  # noqa: E402
from check_external_review_evidence import (  # noqa: E402
    AUTHENTICATION_BOUNDARY,
    RECEIPT_SCHEMA,
    REQUIRED_INDEPENDENT_CHECKS,
    SOURCE_SCHEMA,
    SYNTHETIC_CLASS,
)


def _git_executable() -> str:
    executable = shutil.which("git")
    assert executable is not None
    return str(Path(executable).resolve(strict=True))


def _clean_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(_public_git_environment())
    return environment


def _run_target(
    root: Path,
    target: str,
    arguments: list[str] | None = None,
    *,
    injected_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if injected_environment:
        environment.update(injected_environment)
    command = [
        sys.executable,
        "-I",
        "-S",
        "-B",
        str(root / "scripts" / "runtime_bootstrap.py"),
        "--git-executable",
        _git_executable(),
        "--target",
        str(root / target),
        "--",
        *(arguments or []),
    ]
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(root: Path, *arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        [_git_executable(), *arguments],
        cwd=root,
        env=_clean_git_environment(),
        input=input_text,
        stdin=None if input_text is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_lure(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main")
    (path / "lure.txt").write_text("not the candidate\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "Publish paper and reproducibility companion")
    return path


def test_all_ambient_git_redirections_are_neutralized(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path / "expected")
    lure = _make_lure(tmp_path / "lure")
    assert _git(candidate, "rev-parse", "HEAD") != _git(lure, "rev-parse", "HEAD")
    injected = {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(lure / ".git" / "objects"),
        "GIT_COMMON_DIR": str(lure / ".git"),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.bare",
        "GIT_CONFIG_PARAMETERS": "'core.bare=true'",
        "GIT_CONFIG_VALUE_0": "true",
        "GIT_DIR": str(lure / ".git"),
        "GIT_INDEX_FILE": str(lure / ".git" / "index"),
        "GIT_NAMESPACE": "refs/namespaces/lure",
        "GIT_OBJECT_DIRECTORY": str(lure / ".git" / "objects"),
        "GIT_REPLACE_REF_BASE": "refs/lure-replacements",
        "GIT_WORK_TREE": str(lure),
    }
    result = _run_target(
        candidate,
        "scripts/check_release.py",
        injected_environment=injected,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_local_replace_ref_is_rejected(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    tree = _git(candidate, "rev-parse", "HEAD^{tree}")
    replacement = _git(
        candidate, "commit-tree", tree, "-m", "Synthetic replacement",
    )
    _git(candidate, "replace", "HEAD", replacement)
    result = _run_target(candidate, "scripts/check_release.py")
    assert result.returncode != 0
    assert "replacement refs are forbidden" in result.stderr


@pytest.mark.parametrize("administrative_path", ["grafts", "alternates"])
def test_local_git_administrative_redirect_is_rejected(
    tmp_path: Path, administrative_path: str,
) -> None:
    candidate = _copy_candidate(tmp_path)
    if administrative_path == "grafts":
        path = candidate / ".git" / "info" / "grafts"
        payload = _git(candidate, "rev-parse", "HEAD") + "\n"
    else:
        lure = _make_lure(tmp_path / "lure")
        path = candidate / ".git" / "objects" / "info" / "alternates"
        payload = str(lure / ".git" / "objects") + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    result = _run_target(candidate, "scripts/check_release.py")
    assert result.returncode != 0
    assert administrative_path in result.stderr


def _last_startxref(payload: bytes) -> int:
    rows = re.findall(rb"startxref\s+([0-9]+)\s+%%EOF", payload)
    assert len(rows) == 1
    return int(rows[0])


def _xref_entry(kind: int, field_two: int, field_three: int) -> bytes:
    return (
        bytes([kind])
        + field_two.to_bytes(4, "big")
        + field_three.to_bytes(2, "big")
    )


def _xref_stream_object(
    identifier: int,
    *,
    first_identifier: int,
    entries: bytes,
    size: int,
    previous: int,
    root_identifier: int,
    root_generation: int,
    count: int,
) -> bytes:
    header = (
        f"{identifier} 0 obj\n"
        f"<< /Type /XRef /Size {size} "
        f"/Root {root_identifier} {root_generation} R "
        f"/Prev {previous} /W [1 4 2] "
        f"/Index [{first_identifier} {count}] /Length {len(entries)} >>\n"
        "stream\n"
    ).encode("ascii")
    return header + entries + b"\nendstream\nendobj\n"


def _write_incremental_xref_stream(path: Path, *, object_stream: bool) -> None:
    original = path.read_bytes()
    previous = _last_startxref(original)
    reader = PdfReader(str(path), strict=True)
    size = int(reader.trailer["/Size"])
    root = reader.trailer.raw_get("/Root")
    assert hasattr(root, "idnum") and hasattr(root, "generation")
    base = original.replace(b"%%EOF", b"     ", 1)

    hidden_identifier = size
    first_offset = len(base)
    if object_stream:
        object_stream_identifier = size + 1
        xref_identifier = size + 2
        object_header = f"{hidden_identifier} 0 ".encode("ascii")
        hidden_object = b"<< /Type /Filespec /F (detached.bin) >>"
        compressed = zlib.compress(object_header + hidden_object)
        object_stream_bytes = (
            f"{object_stream_identifier} 0 obj\n"
            f"<< /Type /ObjStm /N 1 /First {len(object_header)} "
            f"/Length {len(compressed)} /Filter /FlateDecode >>\n"
            "stream\n"
        ).encode("ascii") + compressed + b"\nendstream\nendobj\n"
        xref_offset = first_offset + len(object_stream_bytes)
        entries = b"".join(
            (
                _xref_entry(2, object_stream_identifier, 0),
                _xref_entry(1, first_offset, 0),
                _xref_entry(1, xref_offset, 0),
            )
        )
        xref = _xref_stream_object(
            xref_identifier,
            first_identifier=hidden_identifier,
            entries=entries,
            size=xref_identifier + 1,
            previous=previous,
            root_identifier=root.idnum,
            root_generation=root.generation,
            count=3,
        )
        appendix = object_stream_bytes + xref
    else:
        xref_identifier = size + 1
        hidden_payload = (
            b"synthetic absolute path "
            + bytes([88, 58, 92])
            + b"Example\\Repository\\payload.bin"
        )
        compressed = zlib.compress(hidden_payload)
        hidden = (
            f"{hidden_identifier} 0 obj\n"
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>\n"
            "stream\n"
        ).encode("ascii") + compressed + b"\nendstream\nendobj\n"
        xref_offset = first_offset + len(hidden)
        entries = b"".join(
            (
                _xref_entry(1, first_offset, 0),
                _xref_entry(1, xref_offset, 0),
            )
        )
        xref = _xref_stream_object(
            xref_identifier,
            first_identifier=hidden_identifier,
            entries=entries,
            size=xref_identifier + 1,
            previous=previous,
            root_identifier=root.idnum,
            root_generation=root.generation,
            count=2,
        )
        appendix = hidden + xref
    final = (
        base
        + appendix
        + f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(final)


def test_non_whitespace_after_terminal_eof_is_rejected(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    pdf = candidate / PDF.relative_to(ROOT)
    pdf.write_bytes(
        pdf.read_bytes()
        + bytes([88, 58, 92])
        + b"Example\\Repository\\payload.bin"
    )
    result = _run_target(candidate, "scripts/check_release.py")
    assert result.returncode != 0
    assert "non-whitespace bytes after terminal EOF" in result.stderr


def test_unreachable_xref_stream_object_is_scanned(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    pdf = candidate / PDF.relative_to(ROOT)
    _write_incremental_xref_stream(pdf, object_stream=False)
    result = _run_target(candidate, "scripts/check_release.py")
    assert result.returncode != 0
    assert "decoded PDF stream" in result.stderr


def test_compressed_object_stream_member_is_scanned(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    pdf = candidate / PDF.relative_to(ROOT)
    _write_incremental_xref_stream(pdf, object_stream=True)
    result = _run_target(candidate, "scripts/check_release.py")
    assert result.returncode != 0
    assert any(
        token in result.stderr
        for token in ("forbidden PDF object type", "forbidden PDF raw marker")
    ), result.stderr


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ("value = bytes.fromhex('503634')", "fromhex"),
        ("value = data.decode('ascii')", "decode"),
        ("value = base64.b64decode('UDY0')", "b64decode"),
        ("value = chr(80)", "chr"),
        ("value = eval('1')", "eval"),
        ("exec('value=1')", "exec"),
        ("value = compile('1', 'x', 'eval')", "compile"),
    ],
)
def test_bounded_assurance_language_rejects_dynamic_reconstruction(
    source: str, primitive: str,
) -> None:
    with pytest.raises(AssertionError, match=primitive):
        _scan_python_source(
            source, "scripts/synthetic_assurance.py", assurance_language=True,
        )


def test_bounded_assurance_language_folds_concatenated_token() -> None:
    for source in ("value = 'P' + '64'", "value = f'P{64}'"):
        with pytest.raises(AssertionError, match="internal project code"):
            _scan_python_source(
                source, "scripts/synthetic_assurance.py", assurance_language=True,
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _synthetic_evidence(candidate: Path, directory: Path) -> tuple[Path, Path]:
    pdf = candidate / PDF.relative_to(ROOT)
    environment = {
        "git": "synthetic",
        "os": "synthetic",
        "python": "synthetic",
        "review_harness": "synthetic-test-only",
    }
    environment_sha = hashlib.sha256(
        json.dumps(
            environment, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest().upper()
    reviewer = "Synthetic Bound Reviewer Fixture"
    reviewed_at = "2026-08-25T12:00:00+02:00"
    verdict = "PASS_SYNTHETIC_EXACT_REVIEW_ZERO_OPEN_FINDINGS"
    candidate_identities = {
        "checker_sha256": _sha256(candidate / "scripts" / "check_release.py"),
        "commit": _git(candidate, "rev-parse", "HEAD"),
        "manifest_sha256": _sha256(candidate / "MANIFEST_SHA256.txt"),
        "pdf_bytes": pdf.stat().st_size,
        "pdf_pages": len(PdfReader(str(pdf), strict=True).pages),
        "pdf_path": PDF.relative_to(ROOT).as_posix(),
        "pdf_sha256": _sha256(pdf),
        "release_sha256": _sha256(candidate / "RELEASE_SHA256.txt"),
        "tree": _git(candidate, "rev-parse", "HEAD^{tree}"),
    }
    report_fields = {
        "CHECKER_SHA256": candidate_identities["checker_sha256"],
        "END_REVIEW": "TRUE",
        "ENVIRONMENT_SHA256": environment_sha,
        "MANIFEST_SHA256": candidate_identities["manifest_sha256"],
        "PAPER_PDF_SHA256": candidate_identities["pdf_sha256"],
        "RELEASE_SHA256": candidate_identities["release_sha256"],
        "REVIEWED_AT": reviewed_at,
        "REVIEWED_COMMIT": candidate_identities["commit"],
        "REVIEWED_TREE": candidate_identities["tree"],
        "REVIEWER_IDENTIFIER": reviewer,
        "REVIEW_SCHEMA": SOURCE_SCHEMA,
        "VERDICT": verdict,
    }
    report = directory / "review.txt"
    ordered_report_keys = sorted(set(report_fields) - {"END_REVIEW"})
    report.write_text(
        "\n".join(f"{key}: {report_fields[key]}" for key in ordered_report_keys)
        + "\nEND_REVIEW: TRUE\n",
        encoding="utf-8",
        newline="\n",
    )
    receipt = {
        "authentication_boundary": AUTHENTICATION_BOUNDARY,
        "candidate": candidate_identities,
        "environment": environment,
        "evidence_class": SYNTHETIC_CLASS,
        "finding_counts": {
            "accepted": 0,
            "critical": 0,
            "high": 0,
            "low": 0,
            "medium": 0,
            "open": 0,
            "total": 0,
        },
        "independent_checks": sorted(REQUIRED_INDEPENDENT_CHECKS),
        "reviewed_at": reviewed_at,
        "reviewer_identifier": reviewer,
        "schema": RECEIPT_SCHEMA,
        "source_report": {
            "bytes": report.stat().st_size,
            "sha256": _sha256(report),
            "terminal_marker": "END_REVIEW: TRUE",
        },
        "status": "PASS",
        "verdict": verdict,
    }
    receipt_path = directory / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report, receipt_path


def test_synthetic_receipt_requires_explicit_noncredit_mode(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path / "candidate-root")
    evidence = tmp_path / "detached-evidence"
    evidence.mkdir()
    report, receipt = _synthetic_evidence(candidate, evidence)
    arguments = [
        "--report", str(report),
        "--receipt", str(receipt),
        "--root", str(candidate),
    ]
    rejected = _run_target(
        candidate, "scripts/check_external_review_evidence.py", arguments,
    )
    assert rejected.returncode != 0
    assert "synthetic evidence has no external-review authority" in rejected.stderr

    accepted = _run_target(
        candidate,
        "scripts/check_external_review_evidence.py",
        [*arguments, "--allow-synthetic-fixture"],
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "SYNTHETIC EVIDENCE INTEGRITY PASS external_credit=NONE" in accepted.stdout


def test_detached_report_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path / "candidate-root")
    evidence = tmp_path / "detached-evidence"
    evidence.mkdir()
    report, receipt = _synthetic_evidence(candidate, evidence)
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "END_REVIEW: TRUE\n",
            "post-receipt mutation\nEND_REVIEW: TRUE\n",
        ),
        encoding="utf-8",
        newline="\n",
    )
    result = _run_target(
        candidate,
        "scripts/check_external_review_evidence.py",
        [
            "--report", str(report),
            "--receipt", str(receipt),
            "--root", str(candidate),
            "--allow-synthetic-fixture",
        ],
    )
    assert result.returncode != 0
    assert "review report identity mismatch" in result.stderr
