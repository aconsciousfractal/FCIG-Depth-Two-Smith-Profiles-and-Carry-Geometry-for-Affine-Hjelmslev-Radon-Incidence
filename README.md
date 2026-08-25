# Depth-Two Smith Profiles and Carry Geometry for Affine Hjelmslev--Radon Incidence

Companion repository for the paper

> **Depth-Two Smith Profiles and Carry Geometry for Affine
> Hjelmslev--Radon Incidence**<br>
> Oleksiy Babanskyy, 2026.

Paper: [PDF](paper/Depth-Two-Smith-Profiles-and-Carry-Geometry-for-Affine-Hjelmslev-Radon-Incidence.pdf) ·
[LaTeX source](paper/main.tex) · [bibliography](paper/references.bib)

The paper studies the integer point--line incidence matrix of the affine
plane over `Z/p^n Z`, using primitive normal directions modulo units. At depth
two it determines the complete `p`-primary Smith profile for every prime and
proves that the canonical transfer extension is nonsplit. It also gives an
exact two-chart relative-shell presentation and a compatible carry matrix.

## Main depth-two result

For the transpose of the affine incidence matrix `B_2`, the paper proves

```text
coker(B_2^T)_(p)
  = (Z/pZ)^[p^3(p-1)/2]
    direct-sum (Z/p^2Z)^[p(p-1)^2(p+2)/4]
    direct-sum (Z/p^3Z)^[p(p-1)/2].
```

The proof explicitly attributes the imported cyclic Fourier and
complete-ideal ingredients. It does not transfer a projective incidence
matrix to the affine matrix and does not infer the all-prime result from
finite computations.

## What the companion checks

The standalone exact-arithmetic companion reconstructs:

- Smith exponents `0^9,1^4,2^2,3^1` for `(p,n)=(2,2)`;
- Smith exponents `0^36,1^27,2^15,3^3` for `(3,2)`;
- the independent depth-three control `0^30,1^6,2^19,3^6,4^2,5^1` for
  `(2,3)`;
- the manuscript Bockstein controls `u_2=1` and `u_3=0`, explicitly typed as
  controls rather than computational proofs;
- 1600 deterministic local-index comparisons against column HNF;
- equality of recursive and direct complete line lattices for `(2,2)` and
  `(2,3)`;
- invalid-prime, strict-sublattice and reserved-target hostile cases.

The pair `(5,2)` is intentionally rejected before geometry construction. No
result for that pair is shipped.

## Quick verification

Use an isolated Python environment and the hash-locked dependency set. Resolve
the Python and Git executables once, then run release-authoritative checks
through the standard-library bootstrap:

```powershell
python -m pip install --require-hashes -r requirements.lock
$PythonAbsolute = (Get-Command python).Source
$GitAbsolute = (Get-Command git).Source
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
& $PythonAbsolute -I -S -B -O scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --module pytest -- `
  -q -p no:cacheprovider `
  --basetemp "$env:TEMP\fcig-hjelmslev-pytest" `
  tests/test_affine_hjelmslev_radon_smith.py tests/test_release_assurance.py
```

Both verifier runs must end with `PASS`. The test suite is deterministic,
uses no network and writes no scientific result file. See
[REPRODUCE.md](REPRODUCE.md) for the POSIX command, the explicitly
non-assurance optimized-pytest compatibility run, the paper build and the
exact integrity layers.

## Repository layout

| Path | Role |
|---|---|
| `paper/` | article source, cited-only bibliography and title-named PDF |
| `companion/` | standalone exact-arithmetic realization |
| `tests/` | hostile, mutation-sensitive and lattice controls |
| `scripts/` | one-command verifier and fail-closed release checks |
| `docs/` | claim, attribution and reproducibility boundaries |
| `.github/workflows/verify.yml` | Python 3.12--3.14 replay and double paper build |

The release checker also verifies the public article template, A4 geometry,
document language, visible front matter, exactly one terminal PDF EOF marker,
the complete PDF cross-reference/object-stream census, absence of lifecycle
codes, a one-root-commit untagged Git history with a GitHub `noreply` identity,
and an object database with no unreachable objects. Authoritative Git calls
use the recorded executable, explicit Git/worktree paths, replacement-free
semantics and a fixed sanitized environment.

The Python hygiene layer is deliberately bounded. It evaluates constant
string/byte expressions and rejects a documented set of dynamic reconstruction
calls in assurance scripts. It is not represented as a detector for arbitrary
program obfuscation; the exact scope and hostile mutations are documented in
[REPRODUCE.md](REPRODUCE.md).

## Citation, licence and accessibility

- Citation metadata: [CITATION.cff](CITATION.cff).
- Licence boundary: [LICENSE_SCOPE.md](LICENSE_SCOPE.md).
- Dependency notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- Accessibility status: [ACCESSIBILITY.md](ACCESSIBILITY.md).
- Claim boundary: [docs/PUBLIC_CLAIM_BOUNDARY.md](docs/PUBLIC_CLAIM_BOUNDARY.md).
- Detached review evidence: [docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md](docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md).

Copyright in the manuscript is retained by Oleksiy Babanskyy. The MIT licence
applies to the original companion software and supporting documentation, not
to the manuscript or compiled paper.

No novelty, firstness, priority or exhaustive-literature claim is made.
Reviewer-delivered evidence remains detached from the candidate and is
hash-bound to its commit, tree, manifests, checker and PDF. The verifier checks
byte consistency, not reviewer independence; provenance must be confirmed
against the reviewer's original delivery, and no pending review is represented
as a pass.
