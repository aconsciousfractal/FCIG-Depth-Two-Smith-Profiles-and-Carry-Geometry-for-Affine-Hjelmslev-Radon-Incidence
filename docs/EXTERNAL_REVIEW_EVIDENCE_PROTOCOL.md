# External review evidence protocol

External review evidence consists of two files delivered by the reviewer:

1. a UTF-8 source report containing the terminal identity fields and ending
   with the canonical LF line `END_REVIEW: TRUE`;
2. a machine-readable JSON receipt that hashes the entire source report and
   binds the exact candidate commit, tree, manifests, release checker and PDF.

Run the evidence verifier only through the trusted-runtime command documented
in `REPRODUCE.md`. The verifier accepts `--report` and `--receipt` paths
outside the repository. Author adjudication is a separate governance object
and is never an input to this integrity check.

For example, after replacing the three absolute placeholders:

```text
ABSOLUTE_PYTHON -I -S -B scripts/runtime_bootstrap.py \
  --git-executable ABSOLUTE_GIT \
  --target scripts/check_external_review_evidence.py -- \
  --report DETACHED_REPORT --receipt DETACHED_RECEIPT
```

## Integrity and provenance are different

The script proves that supplied evidence bytes agree with one exact clean
candidate. It cannot prove who created or delivered those bytes. External
credit therefore requires the operator to compare their hashes with the
original reviewer-controlled delivery. A Git tag, commit message, author
adjudication or tracked copy cannot establish independence.

The candidate root contains no positive external-review fixture. Tests may
create receipts labelled `SYNTHETIC_TEST_ONLY`; the command requires an
explicit opt-in for them and reports `external_credit=NONE`.

## Required report fields

The report contains exactly one occurrence of each terminal field:

```text
REVIEW_SCHEMA: fcig_affine_hjelmslev_external_review_source_v1
VERDICT: <PASS_OR_HOLD_TOKEN>
REVIEWER_IDENTIFIER: <STABLE_IDENTIFIER>
REVIEWED_AT: <RFC3339_WITH_TIMEZONE>
REVIEWED_COMMIT: <COMMIT>
REVIEWED_TREE: <TREE>
MANIFEST_SHA256: <SHA256>
RELEASE_SHA256: <SHA256>
CHECKER_SHA256: <SHA256>
PAPER_PDF_SHA256: <SHA256>
ENVIRONMENT_SHA256: <CANONICAL_JSON_SHA256>
END_REVIEW: TRUE
```

The receipt schema fixes the corresponding key census, the report byte count
and hash, a complete environment object, finding counts and the independent
check census. A `PASS` receipt cannot retain Critical, High, Medium or open
findings. A syntactically valid `HOLD` remains a review HOLD.

## Tags and descendants

Every candidate is a fresh one-commit parentless root. Tags and corrective
descendants are rejected. A later candidate must be materialized in a new
object database and receive its own detached report and receipt.
