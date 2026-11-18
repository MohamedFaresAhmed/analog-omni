"""Independent check of the legacy reference fixtures (schema omni-legacy-fixture/1).

The fixtures were exported once from the MATLAB small-signal analyser (SCA).
This test never imports production code. It re-stamps each circuit from the
exported component list using only the fixture's conventions block, and checks:

1. index.csv lists exactly the expected fixtures, with matching size and SHA-256;
2. each fixture states the conventions this oracle assumes;
3. the re-stamped G, C and B match the exported matrices;
4. solving the exported (G + s*C) x = B reproduces every stored H sample;
5. solving the re-stamped system reproduces every stored H sample.
"""
import ast
import csv
import functools
import hashlib
import json
import operator
import re
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "legacy"
SCHEMA = "omni-legacy-fixture/1"
EXPECTED_IDS = ("04E-4", "05D", "06", "07", "08", "09")

# Observed on 2026-11-18 with NumPy 2.5: matrices within 1.3e-16, H within
# 6.0e-14 (fixture 09, transfer Hcmd). The limits leave room for other BLAS
# builds while still catching any stamping or sign error.
MATRIX_RTOL = 1e-12  # max |re-stamped - exported| / max |exported|
H_TOL = 1e-10  # max |H - H_stored| / max(1, |H_stored|)


# ---------------------------------------------------------------- loading


@functools.lru_cache(maxsize=None)
def load(test_id):
    with open(FIXTURE_DIR / f"{test_id}.json", encoding="utf-8") as fh:
        return json.load(fh)


def read_index():
    with open(FIXTURE_DIR / "index.csv", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


TRANSFER_CASES = [
    pytest.param(test_id, tr["name"], id=f"{test_id}-{tr['name']}")
    for test_id in EXPECTED_IDS
    for tr in load(test_id)["transfers"]
]


def transfer(fx, name):
    (tr,) = [t for t in fx["transfers"] if t["name"] == name]
    return tr


# ---------------------------------------------------------------- oracle

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate(expr, values):
    """Evaluate +, -, *, /, ^ over named parameters; anything else is rejected."""

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"unsupported expression: {expr!r}")

    return ev(ast.parse(expr.replace("^", "**"), mode="eval"))


def stamp(fx, changes=()):
    """Build G, C and B from the component list, following the conventions block."""
    unknowns = fx["mna"]["unknowns"]
    nodes = unknowns["node_voltages"]
    branches = unknowns["branch_currents"]
    n = len(nodes) + len(branches)
    node_row = {name: i for i, name in enumerate(nodes)}
    branch_row = {name: len(nodes) + i for i, name in enumerate(branches)}
    values = {p["symbol"]: float(p["value"]) for p in fx["parameters"]}
    values[fx["input"]["symbol"]] = float(fx["input"]["value_in_B"])
    override = {(c["component"], c["param"]): c["used"] for c in changes}
    G = np.zeros((n, n))
    C = np.zeros((n, n))
    B = np.zeros(n)
    ground = fx["circuit"]["ground"]

    def row(node):
        return None if node == ground else node_row[node]

    def add(M, r, c, v):
        if r is not None and c is not None:
            M[r, c] += v

    def two_terminal(M, a, b, y):
        add(M, a, a, y)
        add(M, b, b, y)
        add(M, a, b, -y)
        add(M, b, a, -y)

    def vccs(p, nn, pc, nc, g):  # current g*(V(pc) - V(nc)) leaves p, enters nn
        add(G, p, pc, g)
        add(G, p, nc, -g)
        add(G, nn, pc, -g)
        add(G, nn, nc, g)

    for comp in fx["circuit"]["components"]:
        kind = comp["type"]
        pins = [row(x) for x in comp["nodes"]]
        par = {k: override.get((comp["name"], k), v) for k, v in comp["params"].items()}

        def num(key):
            return evaluate(par[key], values)

        if kind == "R":
            two_terminal(G, pins[0], pins[1], 1.0 / num("R"))
        elif kind == "C":
            two_terminal(C, pins[0], pins[1], num("C"))
        elif kind == "V":  # V(plus) - V(minus) = amp; branch current plus -> minus
            r = branch_row[comp["name"]]
            add(G, pins[0], r, 1.0)
            add(G, pins[1], r, -1.0)
            add(G, r, pins[0], 1.0)
            add(G, r, pins[1], -1.0)
            B[r] = num("amp")
        elif kind == "VCCS":
            vccs(*pins, num("g"))
        elif kind == "M":  # pins [D, G, S, B]
            d, g, s, b = pins
            two_terminal(G, d, s, 1.0 / num("ro"))
            vccs(d, s, g, s, num("gm"))
            vccs(d, s, b, s, num("gmb"))
            for key, (x, y) in {
                "cgs": (g, s),
                "cgd": (g, d),
                "cgb": (g, b),
                "cdb": (d, b),
                "csb": (s, b),
            }.items():
                two_terminal(C, x, y, num(key))
        else:
            raise ValueError(f"no stamp for type {kind} ({comp['name']})")
    return G, C, B


def output(fx, x, definition):
    """Read V(a)/in or (V(a)-V(b))/in from the solution; the input is 1 in B."""
    node_row = {name: i for i, name in enumerate(fx["mna"]["unknowns"]["node_voltages"])}
    m = re.fullmatch(r"\(?V\((\w+)\)(?:-V\((\w+)\))?\)?/(\w+)", definition)
    if not m:
        raise ValueError(f"unknown definition {definition!r}")
    if m.group(3) != fx["input"]["symbol"]:
        raise ValueError(f"definition {definition!r} is not over the input symbol")
    out = x[node_row[m.group(1)]]
    if m.group(2):
        out = out - x[node_row[m.group(2)]]
    return out


def sweep(fx, G, C, B, definition):
    return np.array(
        [
            output(fx, np.linalg.solve(G + 2j * np.pi * f * C, B), definition)
            for f in fx["frequencies_hz"]
        ]
    )


def stored_h(tr):
    return np.array(tr["real"], float) + 1j * np.array(tr["imag"], float)


def h_error(h, ref):
    return float(np.max(np.abs(h - ref) / np.maximum(1.0, np.abs(ref))))


def matrix_error(a, ref):
    return float(np.max(np.abs(a - ref)) / np.max(np.abs(ref)))


# ---------------------------------------------------------------- tests


def test_index_lists_exactly_the_expected_fixtures():
    rows = read_index()
    assert [r["Id"] for r in rows] == list(EXPECTED_IDS)
    on_disk = sorted(p.name for p in FIXTURE_DIR.glob("*.json"))
    assert on_disk == sorted(r["File"] for r in rows)


@pytest.mark.parametrize("row", read_index(), ids=lambda r: r["Id"])
def test_index_size_and_hash(row):
    data = (FIXTURE_DIR / row["File"]).read_bytes()
    assert len(data) == int(row["Bytes"])
    assert hashlib.sha256(data).hexdigest().upper() == row["Sha256"].upper()


@pytest.mark.parametrize("test_id", EXPECTED_IDS)
def test_schema_and_conventions(test_id):
    fx = load(test_id)
    assert fx["schema"] == SCHEMA
    assert fx["test_id"] == test_id
    conv = fx["conventions"]
    assert conv["mos_terminal_order"]["nodes"] == ["D", "G", "S", "B"]
    assert conv["vccs"]["nodes"] == ["p", "n", "pc", "nc"]
    assert conv["vccs"]["current"].startswith("I = g*(V(pc) - V(nc)) flows from node p")
    assert conv["voltage_source"]["nodes"] == ["plus", "minus"]
    assert conv["voltage_source"]["constraint"] == "V(plus) - V(minus) = amp"
    assert conv["frequency"]["rule"] == "s = j*2*pi*f, f in Hz"


@pytest.mark.parametrize("test_id", EXPECTED_IDS)
def test_restamped_matrices_match_export(test_id):
    fx = load(test_id)
    G, C, B = stamp(fx)
    assert matrix_error(G, np.array(fx["mna"]["G"], float)) <= MATRIX_RTOL
    assert matrix_error(C, np.array(fx["mna"]["C"], float)) <= MATRIX_RTOL
    np.testing.assert_array_equal(B, np.array(fx["mna"]["B"], float))


@pytest.mark.parametrize("test_id, name", TRANSFER_CASES)
def test_exported_system_reproduces_h(test_id, name):
    fx = load(test_id)
    tr = transfer(fx, name)
    B = np.array(tr.get("B", fx["mna"]["B"]), float)
    G = np.array(fx["mna"]["G"], float)
    C = np.array(fx["mna"]["C"], float)
    assert h_error(sweep(fx, G, C, B, tr["definition"]), stored_h(tr)) <= H_TOL


@pytest.mark.parametrize("test_id, name", TRANSFER_CASES)
def test_restamped_system_reproduces_h(test_id, name):
    fx = load(test_id)
    tr = transfer(fx, name)
    G, C, B = stamp(fx, tr["circuit_changes"])
    np.testing.assert_array_equal(B, np.array(tr.get("B", fx["mna"]["B"]), float))
    assert h_error(sweep(fx, G, C, B, tr["definition"]), stored_h(tr)) <= H_TOL
