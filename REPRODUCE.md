# Reproducing the package

## Supported environment

- Python 3.12, 3.13 or 3.14;
- the exact packages and wheel hashes in `requirements.lock`;
- for the paper: LuaLaTeX, Biber and latexmk;
- for independent PDF inspection: Poppler and pypdf 6.14.2.

The frozen Windows paper build uses MiKTeX 25.12, LuaHBTeX 1.24.0, Biber
2.21 and latexmk 4.88. The GitHub workflow repeats the semantic checks on
Ubuntu with an independent TeX distribution.

## Install the hash-locked Python environment

Create and activate an isolated environment, then run:

```bash
python -m pip install --require-hashes -r requirements.lock
```

`requirements.txt` lists only the three direct dependencies for readability;
it is not the frozen installation contract. Dependency installation may use a
package index. All verification and paper-build commands below are offline.

## Exact replay

Release-authoritative commands must not inherit an ambient Python or Git
repository selection. From the repository root on PowerShell, resolve both
executables and enter through the standard-library bootstrap:

```powershell
$PythonAbsolute = (Get-Command python).Source
$GitAbsolute = (Get-Command git).Source
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
& $PythonAbsolute -I -S -B -O scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/verify.py
```

The POSIX equivalent is:

```bash
PYTHON_ABSOLUTE=$(python -I -S -c 'import sys; print(sys.executable)')
GIT_ABSOLUTE=$(command -v git)
"$PYTHON_ABSOLUTE" -I -S -B scripts/runtime_bootstrap.py \
  --git-executable "$GIT_ABSOLUTE" --target scripts/verify.py
"$PYTHON_ABSOLUTE" -I -S -B -O scripts/runtime_bootstrap.py \
  --git-executable "$GIT_ABSOLUTE" --target scripts/verify.py
```

Both commands print the canonical exact-arithmetic receipt and end with
`PASS`. The optimized run guards against validation that accidentally depends
on Python `assert` statements. The bootstrap itself uses only the standard
library until it has recorded the absolute Python and Git executables and the
installed direct-dependency contents. It strips ambient Python/Git variables,
then passes a minimal environment and a hash-bound runtime context to the
target.

The compact command synopsis in the paper names logical script targets. The
bootstrap invocations in this file are the normative release-authoritative
commands. In particular, direct execution of `scripts/check_release.py`
without a trusted runtime context intentionally fails closed.

The companion can also be run directly:

```bash
python -B companion/affine_hjelmslev_radon_smith.py
```

It reports the three frozen Smith profiles, obstruction curves, the 1600-case
HNF transcript digest, two complete-lattice HNF digests and the typed
Bockstein controls. It creates no output file.

## Hostile suite

On Windows, always provide an explicit writable system-temporary path:

```powershell
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --module pytest -- `
  -q -p no:cacheprovider `
  --basetemp "$env:TEMP\fcig-hjelmslev-pytest" `
  tests/test_affine_hjelmslev_radon_smith.py tests/test_release_assurance.py
```

On POSIX systems use:

```bash
"$PYTHON_ABSOLUTE" -I -S -B scripts/runtime_bootstrap.py \
  --git-executable "$GIT_ABSOLUTE" --module pytest -- \
  -q -p no:cacheprovider \
  --basetemp /tmp/fcig-hjelmslev-pytest \
  tests/test_affine_hjelmslev_radon_smith.py tests/test_release_assurance.py
```

The suite is deterministic and uses neither the network nor data outside the
candidate copy.

For interpreter-optimization compatibility only, Windows reviewers may also
run the following command with a distinct writable temporary directory:

```powershell
& $PythonAbsolute -I -S -B -O scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --module pytest -- `
  -q -p no:cacheprovider `
  --basetemp "$env:TEMP\fcig-hjelmslev-pytest-optimized" `
  tests/test_affine_hjelmslev_radon_smith.py tests/test_release_assurance.py
```

Python optimization removes ordinary `assert` statements from pytest test
bodies. Consequently, a pass from this optional command is only a smoke test
for optimized-interpreter compatibility and adds no assurance. The normal
suite above is the mutation-sensitive assurance run.

## Integrity layers

Run the layers separately through the same boundary with:

```powershell
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/check_manifest.py
& $PythonAbsolute -I -S -B scripts/runtime_bootstrap.py `
  --git-executable $GitAbsolute --target scripts/check_release.py
```

`MANIFEST_SHA256.txt` covers every shipped environment-independent source
file except itself, `RELEASE_SHA256.txt` and the compiled PDF. The release
manifest separately authenticates the source manifest and title-named PDF.

The release checker rejects undeclared files and directories, symlinks,
reparse points, NTFS alternate streams, local-path residue, active or local
PDF actions, visible lifecycle codes, non-A4 output, missing language/front
matter, a nonpublic paper template, a dirty checkout, grafts, replace refs and
alternate object databases. It obtains path, mode and blob identities from the
current `HEAD`, requires an identical stage-zero index, rejects hidden
`assume-unchanged` and `skip-worktree` flags, and hashes every working-tree
file as a raw Git blob before accepting byte identity. Ordinary corrective
commits, merges, tags, remotes and detached CI checkouts remain allowed.

Git is invoked by its recorded absolute path with `--no-replace-objects`,
explicit `--git-dir` and `--work-tree` bindings, and a fixed six-key Git
environment. The checker verifies the resolved worktree, Git directory,
common directory and object directory before trusting history queries.

The PDF layer scans the complete raw file, requires exactly one `%%EOF` with
only PDF whitespace afterward, enumerates the entire xref plus object-stream
members, and inspects all decoded streams and dictionaries. Thus orphaned but
xref-listed objects are not hidden by catalog reachability.

## Bounded Python-assurance scope

The release hygiene scanner folds literal strings and bytes, concatenation,
bounded repetition and constant formatted strings. In assurance scripts it
also rejects calls through `fromhex`, common Base64/Base85 decoders, `decode`,
`chr`, `eval`, `exec` and `compile`. The hostile suite contains a mutation for
each class and for a concatenated internal token.

This is a finite, declared control surface. It is not a proof that arbitrary
Python obfuscation can be recognized. Reviewers should inspect assurance code
as code in addition to running the mutations.

## Detached external-review evidence

The candidate contains no positive review fixture and accepts no review tag.
After review, the reviewer returns a source report and JSON receipt outside
the checkout. To validate their internal byte consistency:

```text
ABSOLUTE_PYTHON -I -S -B scripts/runtime_bootstrap.py \
  --git-executable ABSOLUTE_GIT \
  --target scripts/check_external_review_evidence.py -- \
  --report DETACHED_REPORT --receipt DETACHED_RECEIPT
```

The report must end in its canonical LF terminal marker. The receipt binds the
whole report and exact candidate commit, tree, manifests, checker and PDF. A
synthetic fixture is rejected unless an explicit test-only flag is supplied;
even then it returns no external credit. Hash agreement does not prove who
created the files, so an operator must compare them with the original
reviewer-controlled delivery. Author adjudication remains separate. See
`docs/EXTERNAL_REVIEW_EVIDENCE_PROTOCOL.md`.

## Build the paper

The repository-local `paper/latexmkrc` fixes the title-based job name. On
PowerShell:

```powershell
Set-Location paper
$env:SOURCE_DATE_EPOCH = '1787443200'
$env:FORCE_SOURCE_DATE = '1'
latexmk -silent -lualatex -interaction=nonstopmode -halt-on-error `
  -file-line-error main.tex
```

If MiKTeX reports that Perl is unavailable, temporarily prepend the directory
containing the Git for Windows `perl.exe` executable to the process-local
`PATH`; no machine-wide or repository setting is required.

On a POSIX shell:

```bash
cd paper
export SOURCE_DATE_EPOCH=1787443200
export FORCE_SOURCE_DATE=1
latexmk -silent -lualatex -interaction=nonstopmode -halt-on-error \
  -file-line-error main.tex
```

The output is
`Depth-Two-Smith-Profiles-and-Carry-Geometry-for-Affine-Hjelmslev-Radon-Incidence.pdf`.
Use lowercase `latexmk -c main.tex` to remove intermediates while retaining
that PDF. Uppercase `-C` also removes the PDF and is not the release cleanup
command.

For a deterministic double build, copy the three paper sources to two fresh
temporary directories, apply the same fixed environment and command in each,
then compare the two PDF SHA-256 values. The workflow in
`.github/workflows/verify.yml` automates that independent check and compares
normalized extracted text and page counts with the committed PDF.

Fixed-epoch output is expected to be byte-identical on the declared fixed
toolchain. A different conforming TeX distribution may produce different PDF
bytes while preserving the mathematical content; such a build is a semantic
cross-check, not the release byte identity.

## Accessibility boundary

The PDF is A4, declares `/Lang=en-US`, uses plain running pages and places the
author only in the front matter. It is not claimed to conform to PDF/UA. See
`ACCESSIBILITY.md` and the structured source `paper/main.tex`.

## Proof versus replay

The all-prime theorems are proved in the manuscript. The companion recomputes
bounded exact lattices and profiles and independently checks its local index
eliminator. No finite replay is used as an all-parameter proof.
