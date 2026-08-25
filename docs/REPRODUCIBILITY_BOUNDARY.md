# Reproducibility boundary

## Recomputed from first principles in the companion

The standalone module constructs the bounded affine geometry, cyclotomic
chart blocks, filtered preimage lattices, obstruction curves, recursive line
lattices and local Smith profiles. It cross-checks its local index eliminator
against independent column HNF on 1600 deterministic matrices and compares
two complete recursive line lattices with direct incidence lattices.

No unshipped control file, local checkout path, network service, random source, external
dataset or cached result is read. The module writes no output file.

## Manuscript controls, not computational derivations

The receipt reports `u_2=1` and `u_3=0` as typed manuscript controls. Their
proof is the appendix's Bockstein, fibre-span and filtered-jet argument. The
program does not claim to replace that proof.

## Determinism

The property stream is generated from the public domain-separated seed
`affine-hjelmslev-radon-hnf-property-v1` and is fixed byte-for-byte; its 1600-line conceptual
transcript has SHA-256
`B034902692C686DE339F0C0728AB61EA75E7C8E8090AA7DF34756D02B0CCCAE2`.
The complete-lattice HNF digests are
`7845D3E42299B2DF7C0FE9E60BB7EA34B987E88E8FBEEE905EDB8DB7A3364A76`
for `(2,2)` and
`302046F44218EEDDC2587A5167643AEF1118E3E06888CBCF60D15AFBDE4BE86D`
for `(2,3)`.

## Limits

The finite cases are mutation-sensitive cross-checks, not extrapolation to all
primes or all depths. The reserved `(5,2)` pair is rejected before geometry
construction and is neither computed nor reported. The package makes no
compression, novelty, priority or source-completeness claim.

The source manifest authenticates environment-independent bytes. The release
manifest separately authenticates the compiled PDF because TeX output can
vary across otherwise conforming distributions.

Release-authoritative checks enter through an isolated no-site bootstrap that
records the selected Python and Git executables and dependency contents. Git
commands use an explicit worktree/Git-directory binding, replacement-free
semantics and a six-key sanitized Git environment. The PDF inspection covers
the complete raw byte stream, a single terminal EOF, every xref entry and every
object-stream member, not only objects reachable from the catalog.

The hygiene scanner is intentionally finite: it folds supported constant AST
expressions and rejects the enumerated dynamic reconstruction calls in the
assurance scripts. Its mutation suite establishes those specific controls; it
does not establish resistance to arbitrary Python obfuscation.

Detached review receipts authenticate consistency with a supplied reviewer
report. They do not authenticate the human or system that supplied it.
Independent-review credit therefore also requires an operator comparison with
the original reviewer-controlled delivery.
