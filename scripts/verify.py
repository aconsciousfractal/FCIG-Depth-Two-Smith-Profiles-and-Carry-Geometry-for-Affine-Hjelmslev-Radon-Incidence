#!/usr/bin/env python3
"""One-command integrity and exact-arithmetic verification entry point."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from check_manifest import ROOT, check_manifest
from check_release import check_release


COMPANION = ROOT / "companion" / "affine_hjelmslev_radon_smith.py"
EXPECTED_RECEIPT_SHA256 = (
    "77E59BE0ECCEAF3DA8FAC21F77603CBFC5E9ADEC8DE4BC44FA295398D2F1820B"
)


def _load_companion():
    spec = importlib.util.spec_from_file_location("affine_incidence_companion", COMPANION)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load standalone companion")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    manifest = check_manifest()
    release = check_release()
    receipt = _load_companion().verify()
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()
    if digest != EXPECTED_RECEIPT_SHA256:
        raise AssertionError(f"companion receipt drift: {digest}")
    if manifest["source_files"] != release["source_files"]:
        raise AssertionError("manifest/release source count drift")
    print(canonical)
    print(f"receipt_sha256={digest}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
