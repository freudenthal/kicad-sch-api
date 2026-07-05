"""Loading a schematic adopts the project name its instances already use.

Regression for a KiCad save-crash: ksa defaulted ``Schematic.name`` to
"simple_circuit" on load, so a component *added* to a loaded file serialized
``(instances (project "simple_circuit" ...))`` while the file's own symbols used a
different project name (e.g. "" from circuit-synth). That inconsistent instances
table loads but crashes KiCad on save and corrupts the file. On load we now adopt
the project name the existing instances use, so added components stay consistent.
"""

import pytest

import kicad_sch_api as ksa

pytestmark = pytest.mark.unit


def _project_names(sch):
    names = set()
    for c in sch.components:
        for inst in c._data.instances:
            names.add(inst.project)
    return names


def test_load_adopts_named_project(tmp_path):
    p = tmp_path / "acme.kicad_sch"
    sch = ksa.create_schematic("acme")
    sch.components.add("Device:R", reference="R1", value="1k", position=(50, 50))
    sch.save(str(p))

    reloaded = ksa.load_schematic(str(p))
    assert reloaded.name == "acme"  # adopted, not "simple_circuit"

    reloaded.components.add("Device:R", reference="R2", value="2k", position=(60, 60))
    reloaded.save(str(p))

    final = ksa.load_schematic(str(p))
    # Both the pre-existing and the newly added component share one project name.
    assert _project_names(final) == {"acme"}


def test_load_adopts_empty_project(tmp_path):
    """circuit-synth writes ``(project "")``; a component added after load must also
    get "" (not "simple_circuit"), or the file becomes internally inconsistent and
    KiCad crashes on save. ``create_schematic("")`` can't produce an empty project
    (it falls back to the default), so rewrite a saved file to project "" to mimic
    circuit-synth's output, then add a PWR_FLAG the way the ERC gate does."""
    p = tmp_path / "empty.kicad_sch"
    sch = ksa.create_schematic("acme")
    sch.components.add("Device:R", reference="R1", value="1k", position=(50, 50))
    sch.save(str(p))
    # Simulate a circuit-synth file: all instances use the empty project name.
    text = p.read_text(encoding="utf-8").replace('(project "acme"', '(project ""')
    p.write_text(text, encoding="utf-8")

    reloaded = ksa.load_schematic(str(p))
    assert reloaded.name == ""

    reloaded.components.add(
        "power:PWR_FLAG", reference="#FLG01", value="PWR_FLAG", position=(60, 60)
    )
    reloaded.save(str(p))

    final = ksa.load_schematic(str(p))
    assert _project_names(final) == {""}


def test_empty_schematic_keeps_default(tmp_path):
    """With no components to learn from, the default name is unchanged."""
    p = tmp_path / "blank.kicad_sch"
    ksa.create_schematic("blank").save(str(p))
    reloaded = ksa.load_schematic(str(p))
    assert reloaded.name == "simple_circuit"
