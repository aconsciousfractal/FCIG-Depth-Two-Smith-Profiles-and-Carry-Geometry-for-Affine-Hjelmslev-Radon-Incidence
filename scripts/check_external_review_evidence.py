#!/usr/bin/env python3
"""Validate detached reviewer evidence against one exact candidate root.

This script proves byte and identity consistency.  It cannot prove that an
author did not fabricate the supplied files; external credit therefore also
requires comparison with the original reviewer-controlled delivery.  Author
adjudication is deliberately outside this input protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

from pypdf import PdfReader

from check_manifest import PDF_PATH, ROOT, native_path
from check_release import check_release
from git_boundary import git_output


RECEIPT_SCHEMA = "fcig_affine_hjelmslev_external_review_receipt_v1"
SOURCE_SCHEMA = "fcig_affine_hjelmslev_external_review_source_v1"
AUTHENTICATION_BOUNDARY = (
    "Integrity is hash-bound to the exact candidate and detached report; "
    "reviewer provenance and independence require comparison with the "
    "original reviewer-controlled delivery and are not established by "
    "author-repository bytes, tags or adjudication."
)
EXTERNAL_CLASS = "REVIEWER_DELIVERED_EXTERNAL"
SYNTHETIC_CLASS = "SYNTHETIC_TEST_ONLY"
RECEIPT_KEYS = {
    "authentication_boundary",
    "candidate",
    "environment",
    "evidence_class",
    "finding_counts",
    "independent_checks",
    "reviewed_at",
    "reviewer_identifier",
    "schema",
    "source_report",
    "status",
    "verdict",
}
CANDIDATE_KEYS = {
    "checker_sha256",
    "commit",
    "manifest_sha256",
    "pdf_bytes",
    "pdf_pages",
    "pdf_path",
    "pdf_sha256",
    "release_sha256",
    "tree",
}
SOURCE_REPORT_KEYS = {"bytes", "sha256", "terminal_marker"}
FINDING_COUNT_KEYS = {
    "accepted", "critical", "high", "low", "medium", "open", "total",
}
REQUIRED_INDEPENDENT_CHECKS = {
    "bounded_python_assurance",
    "commit_tree_identity",
    "detached_evidence_protocol",
    "hostile_git_binding",
    "manifest_release_checker_pdf_identity",
    "normal_replay",
    "optimized_replay",
    "pdf_full_object_census",
}
REPORT_KEYS = {
    "CHECKER_SHA256",
    "END_REVIEW",
    "ENVIRONMENT_SHA256",
    "MANIFEST_SHA256",
    "PAPER_PDF_SHA256",
    "RELEASE_SHA256",
    "REVIEWED_AT",
    "REVIEWED_COMMIT",
    "REVIEWED_TREE",
    "REVIEWER_IDENTIFIER",
    "REVIEW_SCHEMA",
    "VERDICT",
}
VERDICT = re.compile(r"(?:PASS|HOLD)_[A-Z0-9_]{20,}")
SHA256 = re.compile(r"[0-9A-F]{64}")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    with native_path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def _object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_receipt(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise AssertionError(f"cannot read review receipt: {error}") from error
    try:
        value = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except ValueError as error:
        raise AssertionError(f"invalid review receipt JSON: {error}") from error
    if not isinstance(value, dict):
        raise AssertionError("review receipt must be a JSON object")
    return value


def _exact_keys(value: object, expected: set[str], *, label: str) -> dict:
    if not isinstance(value, dict):
        raise AssertionError(f"{label} must be an object")
    if set(value) != expected:
        raise AssertionError(
            f"{label} key census drift: missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}"
        )
    return value


def _ascii_text(value: object, *, label: str, minimum: int = 1) -> str:
    if (
        not isinstance(value, str)
        or len(value) < minimum
        or not value.isascii()
        or not value.isprintable()
    ):
        raise AssertionError(f"{label} must be printable ASCII")
    return value


def _timestamp(value: object) -> str:
    text = _ascii_text(value, label="reviewed_at", minimum=20)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise AssertionError("reviewed_at is not RFC 3339") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssertionError("reviewed_at must include a timezone")
    return text


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return sha256_bytes(payload)


def _report_fields(report_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in report_text.splitlines():
        key, separator, value = line.partition(": ")
        if key not in REPORT_KEYS:
            continue
        if not separator or not value or key in fields:
            raise AssertionError(f"malformed or duplicate report field: {key}")
        fields[key] = value
    if set(fields) != REPORT_KEYS:
        raise AssertionError(
            f"report field census drift: missing={sorted(REPORT_KEYS - set(fields))}"
        )
    if fields["END_REVIEW"] != "TRUE":
        raise AssertionError("review report lacks its terminal marker")
    return fields


def _candidate_identities(root: Path) -> dict[str, object]:
    commit = git_output(root, "rev-parse", "HEAD")
    tree = git_output(root, "rev-parse", "HEAD^{tree}")
    pdf = root / Path(*PurePosixPath(PDF_PATH).parts)
    return {
        "checker_sha256": sha256_file(root / "scripts" / "check_release.py"),
        "commit": commit,
        "manifest_sha256": sha256_file(root / "MANIFEST_SHA256.txt"),
        "pdf_bytes": native_path(pdf).stat().st_size,
        "pdf_pages": len(PdfReader(str(native_path(pdf)), strict=True).pages),
        "pdf_path": PDF_PATH,
        "pdf_sha256": sha256_file(pdf),
        "release_sha256": sha256_file(root / "RELEASE_SHA256.txt"),
        "tree": tree,
    }


def validate_external_review_evidence(
    report_path: Path,
    receipt_path: Path,
    *,
    root: Path = ROOT,
    allow_synthetic: bool = False,
) -> dict[str, object]:
    """Validate detached evidence and return a nonpromotional receipt."""

    check_release(root)
    receipt = _exact_keys(load_receipt(receipt_path), RECEIPT_KEYS, label="receipt")
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise AssertionError("review receipt schema drift")
    evidence_class = receipt["evidence_class"]
    if evidence_class not in {EXTERNAL_CLASS, SYNTHETIC_CLASS}:
        raise AssertionError("unknown evidence class")
    if evidence_class == SYNTHETIC_CLASS and not allow_synthetic:
        raise AssertionError("synthetic evidence has no external-review authority")
    if receipt["authentication_boundary"] != AUTHENTICATION_BOUNDARY:
        raise AssertionError("authentication boundary drift")

    reviewer = _ascii_text(
        receipt["reviewer_identifier"], label="reviewer_identifier", minimum=8,
    )
    if reviewer.lower() in {
        "anonymous", "external reviewer", "reviewer", "synthetic reviewer",
    }:
        raise AssertionError("reviewer identifier is not sufficiently specific")
    reviewed_at = _timestamp(receipt["reviewed_at"])

    status = receipt["status"]
    if status not in {"PASS", "HOLD"}:
        raise AssertionError("review status must be PASS or HOLD")
    verdict = _ascii_text(receipt["verdict"], label="verdict", minimum=24)
    if VERDICT.fullmatch(verdict) is None or not verdict.startswith(status + "_"):
        raise AssertionError("review verdict token is noncanonical")

    environment = receipt["environment"]
    if not isinstance(environment, dict) or not environment:
        raise AssertionError("review environment must be a nonempty object")
    for key, value in environment.items():
        _ascii_text(key, label="environment key")
        _ascii_text(value, label=f"environment value {key}")
    environment_sha256 = _canonical_json_sha256(environment)

    counts = _exact_keys(
        receipt["finding_counts"], FINDING_COUNT_KEYS, label="finding_counts",
    )
    if any(not isinstance(value, int) or value < 0 for value in counts.values()):
        raise AssertionError("finding counts must be nonnegative integers")
    if counts["total"] != sum(
        counts[key] for key in ("critical", "high", "medium", "low")
    ):
        raise AssertionError("finding total mismatch")
    if counts["open"] > counts["total"] or counts["accepted"] > counts["total"]:
        raise AssertionError("finding disposition count exceeds total")
    if status == "PASS" and any(
        counts[key] for key in ("critical", "high", "medium", "open")
    ):
        raise AssertionError("PASS cannot retain critical/high/medium/open findings")

    checks = receipt["independent_checks"]
    if (
        not isinstance(checks, list)
        or any(not isinstance(item, str) for item in checks)
        or len(checks) != len(set(checks))
        or set(checks) != REQUIRED_INDEPENDENT_CHECKS
    ):
        raise AssertionError("independent check census drift")

    candidate = _exact_keys(
        receipt["candidate"], CANDIDATE_KEYS, label="candidate identities",
    )
    observed = _candidate_identities(root)
    if candidate != observed:
        raise AssertionError(
            f"candidate identity mismatch: expected={observed}, supplied={candidate}"
        )
    for key in (
        "checker_sha256", "manifest_sha256", "pdf_sha256",
        "release_sha256",
    ):
        if SHA256.fullmatch(str(candidate[key])) is None:
            raise AssertionError(f"noncanonical SHA-256: {key}")

    report_bytes = report_path.read_bytes()
    try:
        report_text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise AssertionError(f"review report is not UTF-8: {error}") from error
    if not report_text.endswith("END_REVIEW: TRUE\n"):
        raise AssertionError(
            "review report must end with its canonical LF terminal marker"
        )
    report = _exact_keys(
        receipt["source_report"], SOURCE_REPORT_KEYS, label="source_report",
    )
    if report != {
        "bytes": len(report_bytes),
        "sha256": sha256_bytes(report_bytes),
        "terminal_marker": "END_REVIEW: TRUE",
    }:
        raise AssertionError("review report identity mismatch")

    fields = _report_fields(report_text)
    expected_fields = {
        "CHECKER_SHA256": str(candidate["checker_sha256"]),
        "END_REVIEW": "TRUE",
        "ENVIRONMENT_SHA256": environment_sha256,
        "MANIFEST_SHA256": str(candidate["manifest_sha256"]),
        "PAPER_PDF_SHA256": str(candidate["pdf_sha256"]),
        "RELEASE_SHA256": str(candidate["release_sha256"]),
        "REVIEWED_AT": reviewed_at,
        "REVIEWED_COMMIT": str(candidate["commit"]),
        "REVIEWED_TREE": str(candidate["tree"]),
        "REVIEWER_IDENTIFIER": reviewer,
        "REVIEW_SCHEMA": SOURCE_SCHEMA,
        "VERDICT": verdict,
    }
    if fields != expected_fields:
        raise AssertionError("review report fields do not match the receipt")

    return {
        "evidence_class": evidence_class,
        "external_credit": "OPERATOR_PROVENANCE_COMPARISON_REQUIRED",
        "report_sha256": report["sha256"],
        "review_status": status,
        "reviewed_commit": candidate["commit"],
        "reviewed_tree": candidate["tree"],
        "status": "INTEGRITY_PASS",
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--allow-synthetic-fixture", action="store_true")
    args = parser.parse_args()
    result = validate_external_review_evidence(
        args.report.resolve(strict=True),
        args.receipt.resolve(strict=True),
        root=args.root.resolve(strict=True),
        allow_synthetic=args.allow_synthetic_fixture,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["evidence_class"] == SYNTHETIC_CLASS:
        print("SYNTHETIC EVIDENCE INTEGRITY PASS external_credit=NONE")
    else:
        print(
            "EXTERNAL REVIEW EVIDENCE INTEGRITY PASS "
            "external_credit=OPERATOR_PROVENANCE_COMPARISON_REQUIRED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
