# Reviewer quickstart

This package separates proof review, computational cross-checking and release
integrity. The paper contains the proofs; the scripts test the shipped bounded
computations and the exact repository surface.

## 1. Verify dependencies and the closed package

```powershell
python -m pip install --require-hashes -r requirements.lock
$PythonAbsolute = (Get-Command python).Source
$GitAbsolute = (Get-Command git).Source
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
& $PythonAbsolute -I -S -B -O scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
```

Each verifier run checks the source manifest, release manifest, public PDF,
Git-history contract and exact companion receipt. Each must end with `PASS`.
No verifier command accesses the network or writes a scientific result file.
The bootstrap records absolute Python/Git identities, clears ambient
Python/Git variables and supplies a minimal subprocess environment.

## 2. Run the hostile suite

```powershell
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --module pytest -- `
  -q -p no:cacheprovider `
  --basetemp "$env:TEMP\fcig-hjelmslev-reviewer-pytest" `
  tests/test_affine_hjelmslev_radon_smith.py tests/test_release_assurance.py
```

The tests reject invalid prime types, the reserved `(5,2)` computational target, strict
sublattices, undeclared paths, reparse points, alternate streams, active PDF
content (including post-EOF and orphan/object-stream payloads), visible
lifecycle codes, an incorrect paper template, ambient Git redirection,
replace/graft/alternate-object rewrites, bounded dynamic Python
reconstruction, synthetic review elevation, hidden index flags and any
HEAD--index--working-tree byte mismatch. They
also check both scaled top-relation products in all three public cases and one
explicit high--high carry coordinate. The optimized pytest command in
[REPRODUCE.md](REPRODUCE.md) is a compatibility smoke test, not an assurance
layer.

## 3. Read the mathematical spine

The principal dependency chain is:

1. maximal-order quotient and canonical depth transition;
2. depth-two structural reduction and finite `p`-group profile recovery;
3. complete-ideal evaluation of the modular rank;
4. exact point-fibre transfer;
5. the all-prime depth-two Smith profile;
6. relative top shell, nonsplitting and the typed two-chart extension.

Four details that should receive particular scrutiny are now written out in
the public paper: equality of the actual and linearized complete-ideal
colengths, the integral domains and codomains of the two-chart block, the
filtered strictness argument in characteristic two, and recovery of every
Smith multiplicity from exact sequences and orders.

The saturation theorem in the appendix is a lateral branch and is not used to
prove the main depth-two quotient. The all-depth filtered identity does not
assert a closed all-depth Smith formula.

## 4. Inspect public boundaries

- [docs/PUBLIC_CLAIM_BOUNDARY.md](docs/PUBLIC_CLAIM_BOUNDARY.md) lists the
  affirmative statements and explicit nonclaims.
- [docs/SOURCE_AND_ATTRIBUTION.md](docs/SOURCE_AND_ATTRIBUTION.md)
  distinguishes imported inputs, adjacent literature and paper-specific
  arguments.
- [docs/REPRODUCIBILITY_BOUNDARY.md](docs/REPRODUCIBILITY_BOUNDARY.md)
  identifies which outputs are recomputed and why bounded replay is not proof.
- [AI_USE.md](AI_USE.md) records the model's mathematical role and the
  author's responsibility for the final content.
- [docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md](docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md)
  specifies the detached report/receipt pair and the provenance boundary.
- [LICENSE_SCOPE.md](LICENSE_SCOPE.md) separates retained manuscript copyright
  from the MIT software and documentation.

No third-party paper, dataset or source tree is bundled.

## 5. Build and inspect the paper

Follow [REPRODUCE.md](REPRODUCE.md). Two clean fixed-epoch builds must be
byte-identical on the declared toolchain. Inspect every rendered page,
equation, table, figure, citation, link and metadata field. The release
checker requires A4 pages, `/Lang=en-US`, plain running pages and the author on
the first page only.

The current PDF is language-marked but is not claimed to conform to PDF/UA;
the exact limitation and source fallback are stated in
[ACCESSIBILITY.md](ACCESSIBILITY.md).

## 6. Return detached evidence

Return a UTF-8 report ending in the required LF terminal marker and a JSON
receipt that hashes the whole report and binds the exact commit, tree,
manifests, checker and PDF. Keep both outside the candidate root. The author
can validate their byte consistency with
`scripts/check_external_review_evidence.py`, but must separately compare them
with your reviewer-controlled delivery: neither a tag nor a tracked copy proves
independence. Author adjudication is a different governance object and is not
an input to the evidence verifier.

## Explicit exclusions

- no full-matrix companion computation or finite certificate at
  `(p,n)=(5,2)`; the uniform theorem itself includes `p=5`;
- no closed Smith profile at arbitrary depth;
- no projective-to-affine incidence-matrix identification;
- no finite-computation proof of an all-prime theorem;
- no compression theorem;
- no novelty, priority or exhaustive source-search conclusion.
