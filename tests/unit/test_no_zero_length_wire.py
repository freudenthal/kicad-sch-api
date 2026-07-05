"""add_wire_between_pins refuses to create a degenerate (zero-length) wire.

Regression for a KiCad save-crash: two pins at the same point (e.g. a multi-pad
sensor's redundant/stacked pads sharing a net) produced a wire whose endpoints
coincide. KiCad loads such a wire but crashes on save and corrupts the file. The
pins are already electrically coincident, so no wire is needed -- the call now
returns None and adds nothing.
"""

import pytest

import kicad_sch_api as ksa

pytestmark = pytest.mark.unit


def test_wire_between_coincident_pins_returns_none(tmp_path):
    sch = ksa.create_schematic("z")
    sch.components.add("Device:R", reference="R1", value="1k", position=(50, 50))

    before = len(list(sch.wires))
    # Wiring a pin to itself is the simplest coincident-endpoint case.
    result = sch.add_wire_between_pins("R1", "1", "R1", "1")

    assert result is None
    assert len(list(sch.wires)) == before  # nothing added

    # And a genuine two-pin wire still works.
    sch.components.add("Device:R", reference="R2", value="2k", position=(50, 60))
    ok = sch.add_wire_between_pins("R1", "2", "R2", "1")
    assert ok is not None
