"""Stage 11.4 acceptance — MCP editing round-trips a circuit-synth schematic.

Certifies the *secondary* editing path from the stage-11 plan: editing a
KiCad-10 schematic that circuit-synth generated, through this server's
consolidated MCP tools (manage_schematic / manage_components / manage_labels /
manage_text_boxes / manage_wires), and verifying the result stays valid:

* it reloads in kicad-sch-api,
* kicad-cli exports a netlist (structural validity KiCad itself accepts),
* the embedded lib_symbols block survives the edit round-trip,
* component values / added parts / removed parts are as expected.

This is the round-trip the plan calls out for foreign / no-Python-source
schematics. On a circuit-synth-*owned* project these edits would be overwritten
by the next regeneration — that boundary is documented, not tested here.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("circuit_synth") is None,
    reason="circuit_synth not installed (needed to generate the source project)",
)

import kicad_sch_api as ksa
from mcp_server.tools.consolidated_tools import (
    manage_components,
    manage_labels,
    manage_schematic,
    manage_text_boxes,
    manage_wires,
)

KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")


def _generate_circuit_synth_project(workdir: Path) -> Path:
    """Generate a small KiCad-10 project with circuit-synth; return its .kicad_sch."""
    from circuit_synth import Component, Net, circuit

    @circuit(name="mcp_roundtrip")
    def divider():
        r1 = Component(symbol="Device:R", ref="R1", value="1k",
                       footprint="Resistor_SMD:R_0603_1608Metric")
        r2 = Component(symbol="Device:R", ref="R2", value="2k",
                       footprint="Resistor_SMD:R_0603_1608Metric")
        vin, vout, gnd = Net("VIN_5V"), Net("VOUT_3V3"), Net("GND")
        r1[1] += vin
        r1[2] += vout
        r2[1] += vout
        r2[2] += gnd

    import os

    cwd = os.getcwd()
    try:
        os.chdir(workdir)
        divider().generate_kicad_project(project_name="mcp_roundtrip",
                                         generate_pcb=False)
    finally:
        os.chdir(cwd)

    sch = workdir / "mcp_roundtrip" / "mcp_roundtrip.kicad_sch"
    assert sch.exists(), f"circuit-synth did not generate {sch}"
    return sch


async def _drive_mcp_edits(sch_path: Path) -> None:
    """Load, apply a representative set of edits, and save via the MCP tools."""
    r = await manage_schematic(action="load", file_path=str(sch_path))
    assert r["success"], r

    # Annotation-class edits (the safe envelope): a label and a text box.
    r = await manage_labels(action="add", text="MCP_NET", position=(60.0, 60.0))
    assert r["success"], r
    r = await manage_text_boxes(action="add", text="rev A (edited via MCP)",
                                position=(10.0, 10.0), size=(40.0, 12.0))
    assert r["success"], r

    # Value edit on an existing component.
    r = await manage_components(action="update", reference="R2", value="6.8k")
    assert r["success"], r

    # Add a component + a wire, then remove the component (exercise both paths).
    r = await manage_components(action="add", lib_id="Device:C", value="100n",
                                reference="C9", position=(120.0, 40.0))
    assert r["success"], r
    r = await manage_wires(action="add", start=(120.0, 50.0), end=(140.0, 50.0))
    assert r["success"], r
    r = await manage_components(action="remove", reference="C9")
    assert r["success"], r

    r = await manage_schematic(action="save")
    assert r["success"], r


@pytest.mark.skipif(not KICAD_CLI.exists(), reason="kicad-cli not installed")
def test_mcp_edit_roundtrip_on_circuit_synth_schematic(tmp_path):
    sch_path = _generate_circuit_synth_project(tmp_path)

    # lib_symbols must be present to begin with (circuit-synth embeds them).
    before = sch_path.read_text(encoding="utf-8")
    assert "(lib_symbols" in before

    asyncio.run(_drive_mcp_edits(sch_path))

    # 1. Reloads cleanly in kicad-sch-api after the MCP edits.
    sch = ksa.Schematic.load(str(sch_path))
    comps = {c.reference: c for c in sch.components}
    assert "R1" in comps and "R2" in comps, f"resistors lost: {list(comps)}"
    assert comps["R2"].value == "6.8k", f"value edit not applied: {comps['R2'].value}"
    assert "C9" not in comps, "removed component C9 still present"
    labels = [getattr(l, "text", None) for l in sch.labels]
    assert "MCP_NET" in labels, f"added label missing: {labels}"

    # 2. Embedded lib_symbols survived the edit round-trip.
    after = sch_path.read_text(encoding="utf-8")
    assert "(lib_symbols" in after, "lib_symbols block dropped by MCP save"
    assert '"Device:R"' in after, "Device:R symbol definition dropped"

    # 3. kicad-cli still exports a netlist (KiCad accepts the file structurally).
    netlist_out = tmp_path / "mcp_roundtrip.net"
    cli = subprocess.run(
        [str(KICAD_CLI), "sch", "export", "netlist",
         "--output", str(netlist_out), str(sch_path)],
        capture_output=True, text=True, timeout=300,
    )
    assert cli.returncode == 0, f"kicad-cli netlist failed:\n{cli.stderr}"
    assert netlist_out.exists()
