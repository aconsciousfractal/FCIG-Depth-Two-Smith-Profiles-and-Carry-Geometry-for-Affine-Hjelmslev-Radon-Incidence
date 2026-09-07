#!/usr/bin/env python3
"""Standalone exact-arithmetic companion for the affine incidence paper.

The module reconstructs bounded Smith-profile controls through explicit
integer lattices.  It is standalone, uses no network service, and writes no
files.  These finite computations are
assurance controls for the mathematical arguments in the paper; they are not
a replacement for those arguments and do not establish literature priority.

The parameter pair ``(p, n) = (5, 2)`` is deliberately unavailable.  Every
entry point validates the prime and rejects that pair before constructing
geometry or allocating a matrix.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from functools import lru_cache
from typing import Iterator, Sequence

import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form


TOP_CASES = ((2, 2), (3, 2), (2, 3), (2, 4))
CARRY_CASES = ((2, 2), (3, 2), (2, 3))
TOWER_CASES = ((2, 2), (3, 2), (2, 3))

EXPECTED_TOP_OBSTRUCTIONS = {
    (2, 2): (0, 0),
    (3, 2): (2, 0),
    (2, 3): (1, 0, 0),
    (2, 4): (6, 0, 1, 0),
}

EXPECTED_CARRY_OBSTRUCTIONS = {
    (2, 2): (1, 1, 0, 0),
    (3, 2): (3, 3, 0, 0),
    (2, 3): (7, 3, 4, 1, 0, 0),
}

EXPECTED_RECURSIVE_PROFILES = {
    (2, 2): Counter({0: 9, 1: 4, 2: 2, 3: 1}),
    (3, 2): Counter({0: 36, 1: 27, 2: 15, 3: 3}),
    (2, 3): Counter({0: 30, 1: 6, 2: 19, 3: 6, 4: 2, 5: 1}),
}

# These two values are theorem-controlled manuscript checks, not outputs of
# the Smith engine below.  The paper supplies their self-contained proof.
BOCKSTEIN_CONTROLS = {2: 1, 3: 0}

# Public, semantic seed for the deterministic assurance stream.  Changing it
# changes only the bounded sample and its transcript digest, never a theorem.
HNF_PROPERTY_SEED = b"affine-hjelmslev-radon-hnf-property-v1"
HNF_PROPERTY_CASE_COUNT = 1600
HNF_PROPERTY_PRIMES = (2, 3, 7)
HNF_PROPERTY_MAX_RANK = 5
HNF_PROPERTY_MAX_EXTRA_COLUMNS = 5
HNF_PROPERTY_MAX_HEIGHT = 5
HNF_PROPERTY_ENTRY_RADIUS_MULTIPLIER = 3
EXPECTED_HNF_PROPERTY_TRANSCRIPT_SHA256 = (
    "B034902692C686DE339F0C0728AB61EA75E7C8E8090AA7DF34756D02B0CCCAE2"
)

WHOLE_LATTICE_CASES = ((2, 2), (2, 3))
EXPECTED_WHOLE_LATTICE_HNF_SHA256 = {
    (2, 2): "7845D3E42299B2DF7C0FE9E60BB7EA34B987E88E8FBEEE905EDB8DB7A3364A76",
    (2, 3): "302046F44218EEDDC2587A5167643AEF1118E3E06888CBCF60D15AFBDE4BE86D",
}


def _validate_prime(p: int) -> None:
    if isinstance(p, bool) or not isinstance(p, int) or not sp.isprime(p):
        raise ValueError("p must be prime")


def reject_reserved_target(p: int, n: int) -> None:
    """Validate ``p`` and reject the unavailable full-matrix check."""

    _validate_prime(p)
    if (p, n) == (5, 2):
        raise AssertionError(
            "reserved (5,2) computational target is intentionally unavailable"
        )


def _phi_prime_power(p: int, n: int) -> int:
    return (p - 1) * p ** (n - 1)


def _projective_directions(p: int, n: int) -> list[tuple[int, int]]:
    q = p**n
    return [(1, slope) for slope in range(q)] + [
        (p * slope, 1) for slope in range(p ** (n - 1))
    ]


@lru_cache(maxsize=None)
def _power_remainders(p: int, n: int) -> tuple[tuple[int, ...], ...]:
    z = sp.symbols("z")
    polynomial = sp.Poly(sp.cyclotomic_poly(p**n, z), z, domain=sp.ZZ)
    degree = polynomial.degree()
    return tuple(
        tuple(
            int(
                sp.Poly(z**exponent, z, domain=sp.ZZ)
                .rem(polynomial)
                .nth(index)
            )
            for index in range(degree)
        )
        for exponent in range(p**n)
    )


def _points(p: int, n: int) -> list[tuple[int, int]]:
    q = p**n
    return [(x, y) for x in range(q) for y in range(q)]


@lru_cache(maxsize=None)
def _incidence_rows(p: int, n: int) -> tuple[tuple[int, ...], ...]:
    reject_reserved_target(p, n)
    q = p**n
    point_list = _points(p, n)
    return tuple(
        tuple(
            int((a * x + b * y) % q == offset)
            for x, y in point_list
        )
        for a, b in _projective_directions(p, n)
        for offset in range(q)
    )


def _p_valuation_mod(value: int, p: int, cutoff: int) -> int:
    value %= p**cutoff
    if value == 0:
        return cutoff
    valuation = 0
    while valuation < cutoff and value % p == 0:
        value //= p
        valuation += 1
    return valuation


def _local_smith_valuations(
    matrix: Sequence[Sequence[int]], p: int, cutoff: int
) -> list[int]:
    """Exact local Smith elimination modulo a resolving power of ``p``."""

    _validate_prime(p)
    modulus = p**cutoff
    work = [[int(value) % modulus for value in row] for row in matrix]
    row_count = len(work)
    column_count = len(work[0]) if work else 0
    if not row_count or not column_count or any(
        len(row) != column_count for row in work
    ):
        raise ValueError("nonempty rectangular matrix required")
    diagonal_length = min(row_count, column_count)
    valuations: list[int] = []
    pivot_index = 0
    while pivot_index < diagonal_length:
        best: tuple[int, int, int] | None = None
        for row in range(pivot_index, row_count):
            for column in range(pivot_index, column_count):
                candidate = (
                    _p_valuation_mod(work[row][column], p, cutoff),
                    row,
                    column,
                )
                if best is None or candidate < best:
                    best = candidate
                    if candidate[0] == 0:
                        break
            if best is not None and best[0] == 0:
                break
        if best is None or best[0] == cutoff:
            break
        valuation, pivot_row, pivot_column = best
        work[pivot_index], work[pivot_row] = work[pivot_row], work[pivot_index]
        if pivot_column != pivot_index:
            for row in work:
                row[pivot_index], row[pivot_column] = (
                    row[pivot_column],
                    row[pivot_index],
                )
        pivot_power = p**valuation
        unit = (work[pivot_index][pivot_index] // pivot_power) % modulus
        inverse = pow(unit, -1, modulus)
        work[pivot_index] = [
            value * inverse % modulus for value in work[pivot_index]
        ]
        for row in range(pivot_index + 1, row_count):
            entry = work[row][pivot_index]
            if entry % pivot_power:
                raise AssertionError("minimal pivot does not divide its column")
            quotient = entry // pivot_power
            if quotient:
                work[row] = [
                    (left - quotient * right) % modulus
                    for left, right in zip(work[row], work[pivot_index])
                ]
        for column in range(pivot_index + 1, column_count):
            entry = work[pivot_index][column]
            if entry % pivot_power:
                raise AssertionError("minimal pivot does not divide its row")
            quotient = entry // pivot_power
            if quotient:
                for row in range(row_count):
                    work[row][column] = (
                        work[row][column]
                        - quotient * work[row][pivot_index]
                    ) % modulus
        valuations.append(valuation)
        pivot_index += 1
    if len(valuations) != diagonal_length:
        raise AssertionError(("unresolved local Smith factors", p, cutoff))
    if valuations != sorted(valuations):
        raise AssertionError("local Smith valuations are not ordered")
    return valuations


def _shell_parameters(p: int, n: int) -> tuple[int, int, int, int]:
    reject_reserved_target(p, n)
    if n < 1:
        raise ValueError("positive depth required")
    q = p**n
    q0 = p ** (n - 1)
    degree = q - q0
    rank = (q + q0) * degree
    return q, q0, degree, rank


@lru_cache(maxsize=None)
def _chart_blocks(
    p: int, n: int
) -> tuple[
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
]:
    """Return the exact two-chart blocks ``A, X, B``."""

    q, q0, degree, _ = _shell_parameters(p, n)
    remainders = _power_remainders(p, n)
    first = tuple(
        tuple(
            remainders[(i + slope * j) % q][basis_index]
            for i in range(degree)
            for j in range(q)
        )
        for slope in range(q)
        for basis_index in range(degree)
    )
    cross = tuple(
        tuple(
            remainders[(p * slope * i + j) % q][basis_index]
            for i in range(degree)
            for j in range(q)
        )
        for slope in range(q0)
        for basis_index in range(degree)
    )
    second = tuple(
        tuple(
            p * remainders[(p * slope * r + i) % q][basis_index]
            for r in range(q0)
            for i in range(degree)
        )
        for slope in range(q0)
        for basis_index in range(degree)
    )
    return first, cross, second


def _line_value(
    p: int,
    n: int,
    direction: tuple[int, int],
    offset: int,
    point: tuple[int, int],
) -> int:
    q = p**n
    return int(
        (direction[0] * point[0] + direction[1] * point[1]) % q == offset
    )


@lru_cache(maxsize=None)
def _carry_generator_rows(p: int, n: int) -> tuple[tuple[int, ...], ...]:
    q, q0, degree, rank = _shell_parameters(p, n)
    coarse_points = [(r, s) for r in range(q0) for s in range(q0)]
    rows = tuple(
        tuple(
            _line_value(p, n, direction, offset, (degree + r, degree + s))
            for r, s in coarse_points
        )
        for direction in _projective_directions(p, n)
        for offset in range(degree)
    )
    if len(rows) != rank or any(len(row) != q0 * q0 for row in rows):
        raise AssertionError(("carry shape", p, n))
    return rows


@lru_cache(maxsize=None)
def _relation_coordinate_matrices(
    p: int, n: int
) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    """Return top-shell and carry coordinates as column matrices."""

    q, q0, degree, rank = _shell_parameters(p, n)
    relation_labels = [
        (direction, offset)
        for direction in _projective_directions(p, n)
        for offset in range(degree)
    ]
    first_rows = []
    for i in range(degree):
        high_i = degree + (i % q0)
        for y in range(q):
            first_rows.append(
                tuple(
                    _line_value(p, n, direction, offset, (i, y))
                    - _line_value(p, n, direction, offset, (high_i, y))
                    for direction, offset in relation_labels
                )
            )
    second_rows = []
    for r in range(q0):
        high_r = degree + r
        for i in range(degree):
            high_i = degree + (i % q0)
            second_rows.append(
                tuple(
                    _line_value(p, n, direction, offset, (high_r, i))
                    - _line_value(p, n, direction, offset, (high_r, high_i))
                    for direction, offset in relation_labels
                )
            )
    carry_columns = tuple(zip(*_carry_generator_rows(p, n)))
    z_matrix = tuple(first_rows + second_rows)
    k_matrix = tuple(tuple(row) for row in carry_columns)
    if len(z_matrix) != rank or any(len(row) != rank for row in z_matrix):
        raise AssertionError(("top-coordinate shape", p, n))
    if len(k_matrix) != q0 * q0 or any(len(row) != rank for row in k_matrix):
        raise AssertionError(("carry-coordinate shape", p, n))
    return z_matrix, k_matrix


@lru_cache(maxsize=None)
def top_relation_matrices(p: int, n: int) -> tuple[sp.Matrix, sp.Matrix]:
    """Return the square top-shell matrix ``T`` and relation matrix ``Z``."""

    reject_reserved_target(p, n)
    if n < 1:
        raise ValueError("positive depth required")
    first, cross, second = _chart_blocks(p, n)
    first_matrix = sp.Matrix(first)
    cross_matrix = sp.Matrix(cross)
    second_matrix = sp.Matrix(second)
    top = first_matrix.row_join(sp.zeros(first_matrix.rows, second_matrix.cols))
    top = top.col_join(cross_matrix.row_join(second_matrix))
    z_rows, _ = _relation_coordinate_matrices(p, n)
    relation = sp.Matrix(z_rows)
    if top.rows != top.cols or relation.shape != top.shape:
        raise AssertionError(("top relation shape", p, n, top.shape, relation.shape))
    return top, relation


def line_coordinate_components(
    p: int,
    n: int,
    direction: tuple[int, int],
    offset: int,
    point: tuple[int, int],
) -> tuple[int, int, int]:
    """Return the first-chart, second-chart and high--high carry summands."""

    reject_reserved_target(p, n)
    if n < 1:
        raise ValueError("positive depth required")
    q, q0, degree, _ = _shell_parameters(p, n)
    directions = _projective_directions(p, n)
    if direction not in directions:
        raise ValueError("direction is not in the canonical affine chart order")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset < degree:
        raise ValueError("offset must lie in the clipped range")
    if (
        len(point) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in point)
        or any(not 0 <= value < q for value in point)
    ):
        raise ValueError("point must have two canonical residue coordinates")

    column = directions.index(direction) * degree + offset
    x, y = point
    z_rows, k_rows = _relation_coordinate_matrices(p, n)
    first = int(z_rows[x * q + y][column]) if x < degree else 0
    second_row = degree * q + (x % q0) * degree + y
    second = int(z_rows[second_row][column]) if y < degree else 0
    carry = int(k_rows[(x % q0) * q0 + (y % q0)][column])
    return first, second, carry


def _integer_matrix(
    values: Sequence[Sequence[int]] | sp.MatrixBase, name: str
) -> sp.Matrix:
    matrix = sp.Matrix(values)
    if not matrix.rows or not matrix.cols:
        raise ValueError(f"{name} must be nonempty")
    if any(value.q != 1 for value in matrix):
        raise ValueError(f"{name} must be integral")
    return matrix.applyfunc(int)


def _modular_rref(
    matrix: sp.Matrix, p: int
) -> tuple[list[list[int]], tuple[int, ...]]:
    work = [
        [int(matrix[row, column]) % p for column in range(matrix.cols)]
        for row in range(matrix.rows)
    ]
    pivot_row = 0
    pivots: list[int] = []
    for column in range(matrix.cols):
        candidate = next(
            (row for row in range(pivot_row, matrix.rows) if work[row][column]),
            None,
        )
        if candidate is None:
            continue
        work[pivot_row], work[candidate] = work[candidate], work[pivot_row]
        inverse = pow(work[pivot_row][column], -1, p)
        work[pivot_row] = [value * inverse % p for value in work[pivot_row]]
        for row in range(matrix.rows):
            if row == pivot_row:
                continue
            multiplier = work[row][column]
            if multiplier:
                work[row] = [
                    (left - multiplier * right) % p
                    for left, right in zip(work[row], work[pivot_row])
                ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == matrix.rows:
            break
    return work, tuple(pivots)


def modular_kernel_split(matrix: sp.Matrix, p: int) -> tuple[sp.Matrix, int]:
    """Construct a unimodular integral lift of a modular kernel split."""

    _validate_prime(p)
    reduced, pivots = _modular_rref(matrix, p)
    pivot_set = set(pivots)
    free = tuple(column for column in range(matrix.cols) if column not in pivot_set)
    columns: list[sp.Matrix] = []
    for column in free:
        vector = sp.zeros(matrix.cols, 1)
        vector[column, 0] = 1
        for pivot_row, pivot_column in enumerate(pivots):
            vector[pivot_column, 0] = (-reduced[pivot_row][column]) % p
        columns.append(vector)
    for pivot_column in pivots:
        vector = sp.zeros(matrix.cols, 1)
        vector[pivot_column, 0] = 1
        columns.append(vector)
    transform = sp.Matrix.hstack(*columns)
    kernel_rank = len(free)
    if transform.shape != (matrix.cols, matrix.cols):
        raise AssertionError("kernel split shape drift")
    for column in range(kernel_rank):
        if any(int(value) % p for value in matrix * transform[:, column]):
            raise AssertionError("purported modular kernel column is nonzero")
    return transform, kernel_rank


def filtered_preimage_bases(
    first: Sequence[Sequence[int]] | sp.MatrixBase, p: int, bound: int
) -> tuple[sp.Matrix, ...]:
    """Return bases of ``{x : first*x is divisible by p**r}``."""

    _validate_prime(p)
    if bound < 0:
        raise ValueError("nonnegative filtration bound required")
    first_matrix = _integer_matrix(first, "first")
    if first_matrix.rows != first_matrix.cols:
        raise ValueError("first must be square")
    width = first_matrix.cols
    basis = sp.eye(width)
    quotient = first_matrix
    bases = [basis]
    for _height in range(1, bound + 1):
        transform, kernel_rank = modular_kernel_split(quotient, p)
        rank = width - kernel_rank
        scale = sp.diag(*([1] * kernel_rank + [p] * rank))
        basis = basis * transform * scale
        transformed = quotient * transform
        next_quotient = sp.zeros(width, width)
        for column in range(kernel_rank):
            for row in range(width):
                value = int(transformed[row, column])
                if value % p:
                    raise AssertionError("kernel column failed integral division")
                next_quotient[row, column] = value // p
        for column in range(kernel_rank, width):
            next_quotient[:, column] = transformed[:, column]
        quotient = next_quotient
        bases.append(basis)
    return tuple(bases)


def _p_primary_index_exponent(
    generators: sp.Matrix, p: int, cutoff: int
) -> int:
    modulus = p**cutoff
    work = [
        [int(generators[row, column]) % modulus for column in range(generators.cols)]
        for row in range(generators.rows)
    ]
    row_count = len(work)
    column_count = len(work[0])
    pivot_index = 0
    valuations: list[int] = []
    while pivot_index < row_count:
        best: tuple[int, int, int] | None = None
        for row in range(pivot_index, row_count):
            for column in range(pivot_index, column_count):
                value = work[row][column]
                valuation = cutoff
                if value:
                    valuation = 0
                    while value % p == 0:
                        value //= p
                        valuation += 1
                candidate = (valuation, row, column)
                if best is None or candidate < best:
                    best = candidate
                    if valuation == 0:
                        break
            if best is not None and best[0] == 0:
                break
        if best is None or best[0] == cutoff:
            raise AssertionError("unresolved local image-lattice factor")
        valuation, pivot_row, pivot_column = best
        work[pivot_index], work[pivot_row] = work[pivot_row], work[pivot_index]
        if pivot_column != pivot_index:
            for row in work:
                row[pivot_index], row[pivot_column] = (
                    row[pivot_column],
                    row[pivot_index],
                )
        pivot_power = p**valuation
        unit = (work[pivot_index][pivot_index] // pivot_power) % modulus
        inverse = pow(unit, -1, modulus)
        work[pivot_index] = [
            value * inverse % modulus for value in work[pivot_index]
        ]
        for row in range(pivot_index + 1, row_count):
            entry = work[row][pivot_index]
            if entry % pivot_power:
                raise AssertionError("minimal local pivot does not divide column")
            quotient = entry // pivot_power
            if quotient:
                work[row] = [
                    (left - quotient * right) % modulus
                    for left, right in zip(work[row], work[pivot_index])
                ]
        for column in range(pivot_index + 1, column_count):
            entry = work[pivot_index][column]
            if entry % pivot_power:
                raise AssertionError("minimal local pivot does not divide row")
            quotient = entry // pivot_power
            if quotient:
                for row in range(row_count):
                    work[row][column] = (
                        work[row][column]
                        - quotient * work[row][pivot_index]
                    ) % modulus
        valuations.append(valuation)
        pivot_index += 1
    if valuations != sorted(valuations):
        raise AssertionError("local image-lattice valuations are not ordered")
    return sum(valuations)


def _deterministic_property_words() -> Iterator[int]:
    counter = 0
    while True:
        block = hashlib.sha256(
            HNF_PROPERTY_SEED + counter.to_bytes(8, "big")
        ).digest()
        for offset in range(0, len(block), 8):
            yield int.from_bytes(block[offset : offset + 8], "big")
        counter += 1


def _p_adic_valuation(value: int, p: int) -> int:
    if value <= 0:
        raise ValueError("valuation input must be positive")
    exponent = 0
    while value % p == 0:
        value //= p
        exponent += 1
    return exponent


def _hnf_p_primary_index_exponent(generators: sp.Matrix, p: int) -> int:
    basis = hermite_normal_form(generators)
    if basis.shape != (generators.rows, generators.rows):
        raise AssertionError(("HNF oracle did not produce a full lattice", basis.shape))
    return _p_adic_valuation(abs(int(basis.det())), p)


def validate_local_index_hnf_property() -> tuple[int, str]:
    """Cross-check 1600 local eliminations against independent column HNF."""

    words = _deterministic_property_words()
    transcript = hashlib.sha256()
    for case_id in range(HNF_PROPERTY_CASE_COUNT):
        p = HNF_PROPERTY_PRIMES[next(words) % len(HNF_PROPERTY_PRIMES)]
        rank = 1 + next(words) % HNF_PROPERTY_MAX_RANK
        extra_columns = next(words) % (HNF_PROPERTY_MAX_EXTRA_COLUMNS + 1)
        height = 1 + next(words) % HNF_PROPERTY_MAX_HEIGHT
        radius = HNF_PROPERTY_ENTRY_RADIUS_MULTIPLIER * p**height
        span = 2 * radius + 1
        data = [next(words) % span - radius for _ in range(rank * extra_columns)]
        dense = (
            sp.Matrix(rank, extra_columns, data)
            if extra_columns
            else sp.zeros(rank, 0)
        )
        generators = dense.row_join(p**height * sp.eye(rank))
        observed = _p_primary_index_exponent(generators, p, height + 1)
        expected = _hnf_p_primary_index_exponent(generators, p)
        if observed != expected:
            raise AssertionError(
                ("local/HNF index mismatch", case_id, p, observed, expected)
            )
        record = [case_id, p, rank, extra_columns, height, data, expected]
        transcript.update(
            json.dumps(record, separators=(",", ":")).encode("ascii") + b"\n"
        )
    digest = transcript.hexdigest().upper()
    if digest != EXPECTED_HNF_PROPERTY_TRANSCRIPT_SHA256:
        raise AssertionError(("deterministic HNF transcript drift", digest))
    return HNF_PROPERTY_CASE_COUNT, digest


def obstruction_length_from_preimage(
    preimage_basis: sp.Matrix,
    cross: Sequence[Sequence[int]] | sp.MatrixBase,
    second: Sequence[Sequence[int]] | sp.MatrixBase,
    p: int,
    height: int,
) -> int:
    _validate_prime(p)
    if height < 1:
        raise ValueError("positive filtration height required")
    cross_matrix = _integer_matrix(cross, "cross")
    second_matrix = _integer_matrix(second, "second")
    if second_matrix.rows != second_matrix.cols:
        raise ValueError("second must be square")
    if cross_matrix.rows != second_matrix.rows:
        raise ValueError("cross codomain does not match second")
    if cross_matrix.cols != preimage_basis.rows or preimage_basis.rows != preimage_basis.cols:
        raise ValueError("cross domain does not match preimage basis")
    modulus = p**height
    denominator = second_matrix.row_join(modulus * sp.eye(second_matrix.rows))
    enlarged = denominator.row_join(cross_matrix * preimage_basis)
    denominator_index = _p_primary_index_exponent(denominator, p, height + 1)
    enlarged_index = _p_primary_index_exponent(enlarged, p, height + 1)
    length = denominator_index - enlarged_index
    if length < 0:
        raise AssertionError("obstruction image has negative length")
    return length


def direct_obstruction_curve(
    first: Sequence[Sequence[int]] | sp.MatrixBase,
    cross: Sequence[Sequence[int]] | sp.MatrixBase,
    second: Sequence[Sequence[int]] | sp.MatrixBase,
    p: int,
    bound: int,
) -> tuple[int, ...]:
    """Compute filtered obstruction-image lengths without a coupled SNF."""

    _validate_prime(p)
    first_matrix = _integer_matrix(first, "first")
    cross_matrix = _integer_matrix(cross, "cross")
    second_matrix = _integer_matrix(second, "second")
    if first_matrix.rows != first_matrix.cols:
        raise ValueError("first must be square")
    if second_matrix.rows != second_matrix.cols:
        raise ValueError("second must be square")
    if cross_matrix.shape != (second_matrix.rows, first_matrix.cols):
        raise ValueError("cross must map the first domain to the second codomain")
    bases = filtered_preimage_bases(first_matrix, p, bound)
    return tuple(
        obstruction_length_from_preimage(
            bases[height], cross_matrix, second_matrix, p, height
        )
        for height in range(1, bound + 1)
    )


@lru_cache(maxsize=None)
def direct_top_obstructions(p: int, n: int) -> tuple[int, ...]:
    reject_reserved_target(p, n)
    first, cross, second = _chart_blocks(p, n)
    return direct_obstruction_curve(first, cross, second, p, n)


@lru_cache(maxsize=None)
def recursive_to_point_transform(p: int, n: int) -> sp.Matrix:
    reject_reserved_target(p, n)
    if n < 2:
        raise ValueError("basis transport starts at depth two")
    q, q0, degree, top_rank = _shell_parameters(p, n)
    fine_rank = q * q
    coarse_rank = q0 * q0
    if coarse_rank + top_rank != fine_rank:
        raise AssertionError("transport rank decomposition drift")
    transform = sp.zeros(fine_rank, fine_rank)
    first_width = degree * q
    for x in range(q):
        for y in range(q):
            row = x * q + y
            transform[row, (x % q0) * q0 + (y % q0)] = 1
            if x < degree:
                transform[row, coarse_rank + x * q + y] = 1
            if y < degree:
                column = coarse_rank + first_width + (x % q0) * degree + y
                transform[row, column] = 1
    return transform


@lru_cache(maxsize=None)
def point_to_recursive_transform(p: int, n: int) -> sp.Matrix:
    reject_reserved_target(p, n)
    if n < 2:
        raise ValueError("basis transport starts at depth two")
    q, q0, degree, top_rank = _shell_parameters(p, n)
    fine_rank = q * q
    coarse_rank = q0 * q0
    inverse = sp.zeros(fine_rank, fine_rank)
    first_width = degree * q
    for r in range(q0):
        for s in range(q0):
            inverse[r * q0 + s, (degree + r) * q + degree + s] = 1
    for i in range(degree):
        high_i = degree + (i % q0)
        for y in range(q):
            row = coarse_rank + i * q + y
            inverse[row, i * q + y] = 1
            inverse[row, high_i * q + y] = -1
    for r in range(q0):
        high_r = degree + r
        for i in range(degree):
            high_i = degree + (i % q0)
            row = coarse_rank + first_width + r * degree + i
            inverse[row, high_r * q + i] = 1
            inverse[row, high_r * q + high_i] = -1
    if coarse_rank + top_rank != fine_rank:
        raise AssertionError("inverse transport rank decomposition drift")
    return inverse


@lru_cache(maxsize=None)
def depth_one_line_presentation(p: int) -> sp.Matrix:
    _validate_prime(p)
    point_list = [(x, y) for x in range(p) for y in range(p)]
    rows = tuple(
        tuple(int((a * x + b * y) % p == offset) for x, y in point_list)
        for a, b in _projective_directions(p, 1)
        for offset in range(p)
    )
    basis = hermite_normal_form(sp.Matrix(rows).T)
    if basis.shape != (p * p, p * p):
        raise AssertionError(("depth-one seed shape", p, basis.shape))
    return basis


@lru_cache(maxsize=None)
def recursive_graph_presentation(p: int, n: int) -> sp.Matrix:
    reject_reserved_target(p, n)
    if n < 2:
        raise ValueError("the graph presentation starts at depth two")
    previous = recursive_line_presentation(p, n - 1)
    z_rows, k_rows = _relation_coordinate_matrices(p, n)
    z_matrix = sp.Matrix(z_rows)
    k_matrix = sp.Matrix(k_rows)
    top = previous.row_join(k_matrix)
    bottom = sp.zeros(z_matrix.rows, previous.cols).row_join(z_matrix)
    graph = top.col_join(bottom)
    expected = p ** (2 * n)
    if graph.shape != (expected, expected):
        raise AssertionError(("recursive graph shape", p, n, graph.shape))
    return graph


@lru_cache(maxsize=None)
def recursive_line_presentation(p: int, n: int) -> sp.Matrix:
    reject_reserved_target(p, n)
    if n < 1:
        raise ValueError("positive depth required")
    if n == 1:
        return depth_one_line_presentation(p)
    return recursive_to_point_transform(p, n) * recursive_graph_presentation(p, n)


def _canonical_integer_matrix_sha256(matrix: sp.Matrix) -> str:
    payload = {
        "rows": matrix.rows,
        "cols": matrix.cols,
        "entries": [int(value) for value in matrix],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest().upper()


def certify_same_column_lattice(
    left: Sequence[Sequence[int]] | sp.MatrixBase,
    right: Sequence[Sequence[int]] | sp.MatrixBase,
    expected_sha256: str | None = None,
) -> str:
    """Certify equality of two full column lattices by canonical column HNF."""

    left_matrix = _integer_matrix(left, "left lattice generators")
    right_matrix = _integer_matrix(right, "right lattice generators")
    if left_matrix.rows != right_matrix.rows:
        raise ValueError("lattice ambient ranks differ")
    left_hnf = hermite_normal_form(left_matrix)
    right_hnf = hermite_normal_form(right_matrix)
    expected_shape = (left_matrix.rows, left_matrix.rows)
    if left_hnf.shape != expected_shape or right_hnf.shape != expected_shape:
        raise AssertionError("whole-lattice control is not full rank")
    if left_hnf != right_hnf:
        raise AssertionError("whole-lattice HNF mismatch")
    digest = _canonical_integer_matrix_sha256(left_hnf)
    if expected_sha256 is not None and digest != expected_sha256:
        raise AssertionError(("whole-lattice canonical digest drift", digest))
    return digest


def validate_whole_lattice_controls() -> dict[tuple[int, int], str]:
    digests: dict[tuple[int, int], str] = {}
    for p, n in WHOLE_LATTICE_CASES:
        recursive = recursive_line_presentation(p, n)
        direct = sp.Matrix(_incidence_rows(p, n)).T
        expected = EXPECTED_WHOLE_LATTICE_HNF_SHA256[(p, n)]
        digests[(p, n)] = certify_same_column_lattice(recursive, direct, expected)
    return digests


@lru_cache(maxsize=None)
def direct_carry_obstructions(p: int, n: int) -> tuple[int, ...]:
    reject_reserved_target(p, n)
    if n < 2:
        raise ValueError("carry obstruction starts at depth two")
    previous = recursive_line_presentation(p, n - 1)
    z_rows, k_rows = _relation_coordinate_matrices(p, n)
    return direct_obstruction_curve(z_rows, k_rows, previous, p, 2 * n)


def _index_length(profile: Counter[int], height: int) -> int:
    return sum(
        max(height - exponent, 0) * multiplicity
        for exponent, multiplicity in profile.items()
    )


def _recover_profile(
    rank: int, curve: Sequence[int], exponent_bound: int
) -> Counter[int]:
    if len(curve) != exponent_bound + 1 or curve[0] != 0:
        raise ValueError("curve must contain its zero-height value")
    profile: Counter[int] = Counter({0: int(curve[1])})
    for exponent in range(1, exponent_bound):
        profile[exponent] = int(
            curve[exponent + 1] - 2 * curve[exponent] + curve[exponent - 1]
        )
    profile[exponent_bound] = int(
        rank - curve[exponent_bound] + curve[exponent_bound - 1]
    )
    profile += Counter()
    if any(value < 0 for value in profile.values()) or sum(profile.values()) != rank:
        raise AssertionError(("invalid recovered profile", rank, curve, profile))
    return profile


@lru_cache(maxsize=None)
def recursive_smith_profile(p: int, n: int) -> Counter[int]:
    """Recover the line-lattice Smith profile from direct obstruction data."""

    reject_reserved_target(p, n)
    if n < 1:
        raise ValueError("positive depth required")
    if n == 1:
        return Counter(_local_smith_valuations(depth_one_line_presentation(p).tolist(), p, 4))
    previous = recursive_smith_profile(p, n - 1)
    z_rows, _ = _relation_coordinate_matrices(p, n)
    relative = Counter(_local_smith_valuations(z_rows, p, 2 * n + 2))
    nu = (0,) + direct_carry_obstructions(p, n)
    curve = tuple(
        _index_length(previous, height)
        + _index_length(relative, height)
        + nu[height]
        for height in range(2 * n + 1)
    )
    return _recover_profile(p ** (2 * n), curve, 2 * n)


def _profile_json(profile: Counter[int]) -> dict[str, int]:
    return {str(exponent): profile[exponent] for exponent in sorted(profile)}


def verify() -> dict[str, object]:
    """Run all frozen controls and return a deterministic JSON-ready receipt."""

    for p, n in TOWER_CASES:
        forward = recursive_to_point_transform(p, n)
        inverse = point_to_recursive_transform(p, n)
        identity = sp.eye(p ** (2 * n))
        if inverse * forward != identity or forward * inverse != identity:
            raise AssertionError(("basis transport inverse", p, n))

    relation_controls = {}
    for p, n in TOWER_CASES:
        top_matrix, relation_matrix = top_relation_matrices(p, n)
        scaled_identity = (p**n) * sp.eye(top_matrix.rows)
        if (
            top_matrix * relation_matrix != scaled_identity
            or relation_matrix * top_matrix != scaled_identity
        ):
            raise AssertionError(("two-sided top relation identity", p, n))
        relation_controls[f"p{p}_n{n}"] = {
            "rank": top_matrix.rows,
            "scale": p**n,
        }

    coordinate_components = line_coordinate_components(2, 2, (1, 1), 0, (0, 0))
    if coordinate_components != (1, -1, 1) or sum(coordinate_components) != 1:
        raise AssertionError(("high-high carry coordinate", coordinate_components))

    top = {}
    for case in TOP_CASES:
        observed = direct_top_obstructions(*case)
        if observed != EXPECTED_TOP_OBSTRUCTIONS[case]:
            raise AssertionError(("direct top obstruction", case, observed))
        top[f"p{case[0]}_n{case[1]}"] = list(observed)

    carry = {}
    profiles = {}
    for case in CARRY_CASES:
        observed = direct_carry_obstructions(*case)
        if observed != EXPECTED_CARRY_OBSTRUCTIONS[case]:
            raise AssertionError(("direct carry obstruction", case, observed))
        profile = recursive_smith_profile(*case)
        if profile != EXPECTED_RECURSIVE_PROFILES[case]:
            raise AssertionError(("recursive Smith profile", case, profile))
        key = f"p{case[0]}_n{case[1]}"
        carry[key] = list(observed)
        profiles[key] = _profile_json(profile)

    property_cases, transcript = validate_local_index_hnf_property()
    lattice_digests = validate_whole_lattice_controls()

    for action in (
        lambda: direct_top_obstructions(5, 2),
        lambda: top_relation_matrices(5, 2),
        lambda: line_coordinate_components(5, 2, (1, 0), 0, (0, 0)),
        lambda: recursive_to_point_transform(5, 2),
        lambda: point_to_recursive_transform(5, 2),
        lambda: recursive_graph_presentation(5, 2),
        lambda: recursive_line_presentation(5, 2),
        lambda: direct_carry_obstructions(5, 2),
        lambda: recursive_smith_profile(5, 2),
    ):
        try:
            action()
        except AssertionError as exc:
            if "reserved (5,2)" not in str(exc):
                raise
        else:
            raise AssertionError("reserved target was not rejected")

    return {
        "status": "PASS",
        "assurance_is_mathematical_proof": False,
        "top_obstructions": top,
        "top_relation_scaled_inverse": relation_controls,
        "carry_obstructions": carry,
        "carry_coordinate_regression": {
            "case": "p2_n2",
            "direction": [1, 1],
            "offset": 0,
            "point": [0, 0],
            "components": list(coordinate_components),
            "value": sum(coordinate_components),
        },
        "smith_profiles_by_p_exponent": profiles,
        "bockstein_manuscript_controls": {
            "u2": BOCKSTEIN_CONTROLS[2],
            "u3": BOCKSTEIN_CONTROLS[3],
        },
        "deterministic_hnf_property": {
            "cases": property_cases,
            "transcript_sha256": transcript,
        },
        "whole_lattice_hnf_sha256": {
            f"p{p}_n{n}": digest
            for (p, n), digest in sorted(lattice_digests.items())
        },
        "reserved_p5_n2_constructed": False,
        "reserved_p5_n2_executed": False,
    }


def main() -> int:
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
