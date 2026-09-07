from __future__ import annotations

import io
import hashlib
import importlib.util
import itertools
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import sympy as sp
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "companion" / "affine_hjelmslev_radon_smith.py"
CHECK_RELEASE = ROOT / "scripts" / "check_release.py"
PDF = ROOT / "paper" / (
    "Depth-Two-Smith-Profiles-and-Carry-Geometry-for-"
    "Affine-Hjelmslev-Radon-Incidence.pdf"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("affine_incidence_companion", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()


def _clear_caches() -> None:
    for value in vars(M).values():
        cache_clear = getattr(value, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()


def test_hostile_prime_inputs_fail_before_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actions = (
        lambda p: M.reject_reserved_target(p, 2),
        lambda p: M.modular_kernel_split(sp.eye(1), p),
        lambda p: M.filtered_preimage_bases(((1,),), p, 1),
        lambda p: M.obstruction_length_from_preimage(
            sp.eye(1), ((1,),), ((1,),), p, 1
        ),
        lambda p: M.direct_obstruction_curve(((1,),), ((1,),), ((1,),), p, 1),
        lambda p: M.direct_top_obstructions(p, 2),
        lambda p: M.top_relation_matrices(p, 2),
        lambda p: M.line_coordinate_components(p, 2, (1, 0), 0, (0, 0)),
        lambda p: M.recursive_to_point_transform(p, 2),
        lambda p: M.point_to_recursive_transform(p, 2),
        lambda p: M.depth_one_line_presentation(p),
        lambda p: M.recursive_graph_presentation(p, 2),
        lambda p: M.recursive_line_presentation(p, 2),
        lambda p: M.direct_carry_obstructions(p, 2),
        lambda p: M.recursive_smith_profile(p, 2),
    )
    _clear_caches()

    def reject_late_work(*_args, **_kwargs):
        raise AssertionError("late geometry or matrix work")

    monkeypatch.setattr(M, "_integer_matrix", reject_late_work)
    monkeypatch.setattr(M, "_modular_rref", reject_late_work)
    monkeypatch.setattr(M, "_chart_blocks", reject_late_work)
    monkeypatch.setattr(M, "_shell_parameters", reject_late_work)
    monkeypatch.setattr(M, "_relation_coordinate_matrices", reject_late_work)
    monkeypatch.setattr(M, "_projective_directions", reject_late_work)
    monkeypatch.setattr(M, "hermite_normal_form", reject_late_work)

    for invalid_p in (4, 9, True, False, 2.0):
        for action in actions:
            with pytest.raises(ValueError, match="p must be prime"):
                action(invalid_p)


def test_reserved_target_fails_before_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_caches()

    def reject_late_work(*_args, **_kwargs):
        raise AssertionError("geometry was constructed")

    monkeypatch.setattr(M, "_chart_blocks", reject_late_work)
    monkeypatch.setattr(M, "_shell_parameters", reject_late_work)
    monkeypatch.setattr(M, "_relation_coordinate_matrices", reject_late_work)
    monkeypatch.setattr(M, "_incidence_rows", reject_late_work)
    for action in (
        lambda: M.direct_top_obstructions(5, 2),
        lambda: M.top_relation_matrices(5, 2),
        lambda: M.line_coordinate_components(5, 2, (1, 0), 0, (0, 0)),
        lambda: M.recursive_to_point_transform(5, 2),
        lambda: M.point_to_recursive_transform(5, 2),
        lambda: M.recursive_graph_presentation(5, 2),
        lambda: M.recursive_line_presentation(5, 2),
        lambda: M.direct_carry_obstructions(5, 2),
        lambda: M.recursive_smith_profile(5, 2),
    ):
        with pytest.raises(AssertionError, match=r"reserved \(5,2\)"):
            action()


def _residue_image(matrix: sp.Matrix, modulus: int) -> set[tuple[int, ...]]:
    return {
        tuple(int(value) % modulus for value in matrix * sp.Matrix(vector))
        for vector in itertools.product(range(modulus), repeat=matrix.cols)
    }


def _kernel_residues(matrix: sp.Matrix, modulus: int) -> set[tuple[int, ...]]:
    return {
        vector
        for vector in itertools.product(range(modulus), repeat=matrix.cols)
        if all(int(value) % modulus == 0 for value in matrix * sp.Matrix(vector))
    }


def test_filtered_preimages_are_exact_on_a_tiny_control() -> None:
    first = sp.Matrix(((2, 1), (0, 4)))
    bases = M.filtered_preimage_bases(first, 2, 3)
    for height in range(1, 4):
        modulus = 2**height
        assert _residue_image(bases[height], modulus) == _kernel_residues(
            first, modulus
        )


def test_modular_kernel_split_is_unimodular() -> None:
    matrix = sp.Matrix(((2, 1, 4), (1, 1, 0)))
    transform, kernel_rank = M.modular_kernel_split(matrix, 3)
    assert abs(int(transform.det())) == 1
    assert kernel_rank == 1
    assert all(
        int(value) % 3 == 0
        for value in matrix * transform[:, :kernel_rank]
    )


def test_expected_obstruction_curves_and_profiles() -> None:
    for case, expected in M.EXPECTED_TOP_OBSTRUCTIONS.items():
        assert M.direct_top_obstructions(*case) == expected
    for case, expected in M.EXPECTED_CARRY_OBSTRUCTIONS.items():
        assert M.direct_carry_obstructions(*case) == expected
        assert M.recursive_smith_profile(*case) == M.EXPECTED_RECURSIVE_PROFILES[case]


@pytest.mark.parametrize("case", M.TOWER_CASES)
def test_top_relation_is_a_two_sided_scaled_inverse(
    case: tuple[int, int],
) -> None:
    p, n = case
    top, relation = M.top_relation_matrices(p, n)
    expected = (p**n) * sp.eye(top.rows)
    assert top * relation == expected
    assert relation * top == expected


def test_high_high_coordinate_carry_identity() -> None:
    components = M.line_coordinate_components(2, 2, (1, 1), 0, (0, 0))
    assert components == (1, -1, 1)
    assert sum(components) == M._line_value(2, 2, (1, 1), 0, (0, 0)) == 1


def test_bockstein_manuscript_controls_are_typed_as_controls() -> None:
    assert M.BOCKSTEIN_CONTROLS == {2: 1, 3: 0}
    assert M.verify()["assurance_is_mathematical_proof"] is False


def test_deterministic_local_eliminator_matches_hnf() -> None:
    assert M.validate_local_index_hnf_property() == (
        1600,
        "B034902692C686DE339F0C0728AB61EA75E7C8E8090AA7DF34756D02B0CCCAE2",
    )


def test_recursive_and_direct_complete_lattices_agree() -> None:
    assert M.validate_whole_lattice_controls() == {
        (2, 2): "7845D3E42299B2DF7C0FE9E60BB7EA34B987E88E8FBEEE905EDB8DB7A3364A76",
        (2, 3): "302046F44218EEDDC2587A5167643AEF1118E3E06888CBCF60D15AFBDE4BE86D",
    }


def test_whole_lattice_certificate_rejects_a_strict_sublattice() -> None:
    recursive = M.recursive_line_presentation(2, 2).copy()
    recursive[:, 0] = 2 * recursive[:, 0]
    direct = sp.Matrix(M._incidence_rows(2, 2)).T
    with pytest.raises(AssertionError, match="whole-lattice HNF mismatch"):
        M.certify_same_column_lattice(recursive, direct)


def test_standalone_source_has_no_private_dependency_surface() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "importlib.util",
        "TARGET_NAMESPACE",
        "REGISTRY",
    )
    assert all(token not in source for token in forbidden)
    assert (
        'HNF_PROPERTY_SEED = b"affine-hjelmslev-radon-hnf-property-v1"'
        in source
    )
    assert "HNF_PROPERTY_SEED_HEX" not in source


def test_full_receipt_is_deterministic_and_complete() -> None:
    first = M.verify()
    second = M.verify()
    assert first == second
    assert first["status"] == "PASS"
    assert first["bockstein_manuscript_controls"] == {"u2": 1, "u3": 0}
    assert first["reserved_p5_n2_constructed"] is False
    assert first["reserved_p5_n2_executed"] is False


def _native_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    absolute = str(path.resolve())
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _public_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_AUTHOR_NAME": "Oleksiy Babanskyy",
            "GIT_AUTHOR_EMAIL": "aconsciousfractal@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "Oleksiy Babanskyy",
            "GIT_COMMITTER_EMAIL": "aconsciousfractal@users.noreply.github.com",
        }
    )
    return environment


def _copy_candidate(tmp_path: Path) -> Path:
    target = tmp_path / "candidate"
    scan_root = _native_path(ROOT)
    for walk_root, directories, files in os.walk(scan_root):
        directories[:] = sorted(
            name
            for name in directories
            if name not in {".git", ".pytest_cache", "__pycache__"}
        )
        source_directory = Path(walk_root)
        relative = source_directory.relative_to(scan_root)
        destination_directory = target / relative
        destination_directory.mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            shutil.copyfile(
                source_directory / name,
                _native_path(destination_directory / name),
            )
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=target,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=target,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Publish paper and reproducibility companion"],
        cwd=target,
        env=_public_git_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    return target


def _run_release(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    git_executable = shutil.which("git")
    assert git_executable is not None
    git_executable = str(Path(git_executable).resolve(strict=True))
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(root / "scripts" / "runtime_bootstrap.py"),
            "--git-executable",
            git_executable,
            "--target",
            str(root / "scripts" / "check_release.py"),
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def test_canonical_release_checker_passes() -> None:
    result = _run_release(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_release_checker_accepts_a_clean_one_root_candidate(
    tmp_path: Path,
) -> None:
    candidate = _copy_candidate(tmp_path)
    result = _run_release(candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_release_checker_rejects_nested_git_directory(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    (candidate / "docs" / ".git").mkdir()
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "directory drift" in result.stderr


def test_release_checker_rejects_public_article_template_drift(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    manuscript = candidate / "paper" / "main.tex"
    text = manuscript.read_text(encoding="utf-8")
    text = text.replace(
        "\\documentclass[12pt,a4paper]{article}",
        "\\documentclass{amsart}",
        1,
    )
    manuscript.write_text(text, encoding="utf-8", newline="\n")
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "public manuscript template drift" in result.stderr


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        ("\n$qquad$\n", "bare TeX spacing command"),
        ("\n$quad$\n", "bare TeX spacing command"),
        ("\n$x^{,y}$\n", "malformed TeX superscript"),
    ],
)
def test_release_checker_rejects_malformed_tex_tokens(
    tmp_path: Path,
    mutation: str,
    diagnostic: str,
) -> None:
    candidate = _copy_candidate(tmp_path)
    manuscript = candidate / "paper" / "main.tex"
    with manuscript.open("a", encoding="utf-8", newline="") as handle:
        handle.write(mutation)
    result = _run_release(candidate)
    assert result.returncode != 0
    assert diagnostic in result.stderr


def test_release_checker_accepts_a_linear_successor(
    tmp_path: Path,
) -> None:
    candidate = _copy_candidate(tmp_path)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Document follow-up"],
        cwd=candidate,
        env=_public_git_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    result = _run_release(candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_release_checker_accepts_tags_and_remotes(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    environment = _public_git_environment()
    subprocess.run(
        ["git", "tag", "-a", "synthetic-review", "-m", "fabricated pass"],
        cwd=candidate,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/repository"],
        cwd=candidate,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    result = _run_release(candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_release_checker_treats_commit_identity_as_metadata(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": "Oleksiy Babanskyy",
            "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
            "GIT_COMMITTER_NAME": "Oleksiy Babanskyy",
            "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
        }
    )
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit", "--reset-author"],
        cwd=candidate,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    result = _run_release(candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


def test_release_checker_ignores_unreachable_objects_outside_head(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=candidate,
        input=b"synthetic unreachable object\n",
        capture_output=True,
        check=True,
    )
    result = _run_release(candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RELEASE PASS" in result.stdout


@pytest.mark.parametrize(
    "parts",
    [
        ("X:", "\\Example\\Repository"),
        ("/.private", "-marker/"),
        ("PROJECT-", "999-GATE"),
    ],
)
def test_release_checker_folds_synthetic_python_string_leaks(
    tmp_path: Path,
    parts: tuple[str, str],
) -> None:
    candidate = _copy_candidate(tmp_path)
    companion = candidate / SCRIPT.relative_to(ROOT)
    mutation = f"\nSYNTHETIC_LEAK = {parts[0]!r} + {parts[1]!r}\n"
    with companion.open("a", encoding="utf-8", newline="") as handle:
        handle.write(mutation)
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "static-constant" in result.stderr


def test_release_checker_scans_its_own_shipped_source(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    checker = candidate / CHECK_RELEASE.relative_to(ROOT)
    mutation = "\nSYNTHETIC_SELF_LEAK = " + repr("X:") + " + " + repr("\\Example\\Repository") + "\n"
    with checker.open("a", encoding="utf-8", newline="") as handle:
        handle.write(mutation)
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "static-constant" in result.stderr


def test_release_checker_rejects_an_undeclared_empty_directory(
    tmp_path: Path,
) -> None:
    candidate = _copy_candidate(tmp_path)
    (candidate / "undeclared-empty").mkdir()
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "directory drift" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="NTFS alternate streams are Windows-only")
def test_release_checker_rejects_an_ntfs_alternate_stream(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    stream_path = str(candidate / "README.md") + ":adversarial"
    with open(stream_path, "wb") as handle:
        handle.write(b"undeclared stream")
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "alternate stream" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-only")
def test_release_checker_rejects_a_windows_junction(tmp_path: Path) -> None:
    candidate = _copy_candidate(tmp_path)
    target = tmp_path / "junction-target"
    target.mkdir()
    junction = candidate / "undeclared-junction"
    subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    try:
        result = _run_release(candidate)
        assert result.returncode != 0
        assert "reparse point" in result.stderr
    finally:
        os.rmdir(junction)


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-only")
def test_release_checker_rejects_a_whole_root_junction(tmp_path: Path) -> None:
    target = _copy_candidate(tmp_path)
    junction = tmp_path / "candidate-root-junction"
    subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    try:
        result = _run_release(junction)
        assert result.returncode != 0
        assert "repository root cannot be a reparse point" in result.stderr
    finally:
        os.rmdir(junction)


def _add_indirect_link_action(writer: PdfWriter, action: DictionaryObject) -> None:
    action_reference = writer._add_object(action)
    annotation = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
            ),
            NameObject("/A"): action_reference,
        }
    )
    annotation_reference = writer._add_object(annotation)
    page = writer.pages[0]
    if "/Annots" not in page:
        page[NameObject("/Annots")] = ArrayObject()
    annotations = page["/Annots"]
    if hasattr(annotations, "get_object"):
        annotations = annotations.get_object()
    annotations.append(annotation_reference)


def _add_visible_governance_code(path: Path) -> None:
    reader = PdfReader(io.BytesIO(path.read_bytes()), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    page = writer.pages[0]

    resources = page["/Resources"]
    if hasattr(resources, "get_object"):
        resources = resources.get_object()
    fonts = resources.get("/Font")
    if fonts is None:
        fonts = DictionaryObject()
        resources[NameObject("/Font")] = fonts
    elif hasattr(fonts, "get_object"):
        fonts = fonts.get_object()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    fonts[NameObject("/SyntheticFont")] = writer._add_object(font)

    visible_code = "-".join(("M", "T07"))
    stream = DecodedStreamObject()
    stream.set_data(
        f"BT /SyntheticFont 8 Tf 18 18 Td ({visible_code}) Tj ET".encode("ascii")
    )
    stream_reference = writer._add_object(stream)
    contents = page.get("/Contents")
    if contents is None:
        page[NameObject("/Contents")] = stream_reference
    elif isinstance(contents, ArrayObject):
        contents.append(stream_reference)
    else:
        page[NameObject("/Contents")] = ArrayObject([contents, stream_reference])

    with path.open("wb") as handle:
        writer.write(handle)


def test_release_checker_rejects_visible_pdf_governance_codes(
    tmp_path: Path,
) -> None:
    candidate = _copy_candidate(tmp_path)
    pdf = candidate / PDF.relative_to(ROOT)
    _add_visible_governance_code(pdf)
    result = _run_release(candidate)
    assert result.returncode != 0
    assert "visible governance code in PDF" in result.stderr


def _mutate_pdf(path: Path, mutation: str) -> None:
    reader = PdfReader(io.BytesIO(path.read_bytes()), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    if mutation == "javascript":
        _add_indirect_link_action(
            writer,
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/JavaScript"),
                    NameObject("/JS"): TextStringObject("app.alert('x')"),
                }
            ),
        )
    elif mutation == "launch":
        _add_indirect_link_action(
            writer,
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/Launch"),
                    NameObject("/F"): TextStringObject("payload.exe"),
                }
            ),
        )
    elif mutation == "local-uri":
        _add_indirect_link_action(
            writer,
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/URI"),
                    NameObject("/URI"): TextStringObject(
                        "file:///synthetic/private/payload.txt"
                    ),
                }
            ),
        )
    elif mutation == "attachment":
        writer.add_attachment("payload.txt", b"undeclared attachment")
    else:
        raise AssertionError(f"unknown PDF mutation: {mutation}")
    with path.open("wb") as handle:
        writer.write(handle)


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        (
            "javascript",
            ("forbidden PDF raw marker", "forbidden PDF key", "forbidden PDF action"),
        ),
        ("attachment", ("EmbeddedFiles", "EmbeddedFile", "PDF key")),
        ("launch", ("forbidden PDF raw marker", "forbidden PDF action")),
        ("local-uri", ("local or malformed PDF URI",)),
    ],
)
def test_release_checker_rejects_structured_active_pdf_mutations(
    tmp_path: Path,
    mutation: str,
    diagnostic: tuple[str, ...],
) -> None:
    candidate = _copy_candidate(tmp_path)
    pdf = candidate / PDF.relative_to(ROOT)
    _mutate_pdf(pdf, mutation)
    result = _run_release(candidate)
    assert result.returncode != 0
    assert any(token in result.stderr for token in diagnostic), result.stderr
