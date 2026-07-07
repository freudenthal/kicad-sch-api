"""Enforce loop-boundary rule R1 (Stage 16): the MCP server is circuit_synth-free.

The kicad-sch-api MCP server (`mcp_server/`, the server Claude Desktop actually
connects to) is the *language-agnostic* editing surface of the design loop — it
operates on `.kicad_sch` files via kicad-sch-api and must never depend on the
circuit_synth DSL. Keeping it clean is what lets a future DSL swap (e.g. SKiDL)
reuse it untouched. Canonical contract: `workingdocs/design_considerations/loop-boundary-contract.md`
(in the sibling `circ-synth/` working tree), rule R1.

Pure file read; fast; dependency-free.
"""

from pathlib import Path

# kicad-sch-api repo root: .../kicad-sch-api/tests/mcp/<this file>
REPO = Path(__file__).resolve().parents[2]
MCP_SERVER = REPO / "mcp_server"


def _server_py_files():
    return [
        p
        for p in MCP_SERVER.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def test_mcp_server_dir_exists():
    assert MCP_SERVER.is_dir(), f"expected MCP server package at {MCP_SERVER}"


def test_r1_mcp_server_has_no_circuit_synth_reference():
    offenders = []
    for path in _server_py_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "circuit_synth" in line or "circuit-synth" in line:
                offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "MCP server must not reference circuit_synth (loop-boundary rule R1); "
        "it speaks .kicad_sch + kicad-sch-api only:\n" + "\n".join(offenders)
    )
