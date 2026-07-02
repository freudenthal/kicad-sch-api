"""Tests for preservation of embedded ``lib_symbols`` definitions.

Historically the parser discarded the embedded ``lib_symbols`` block on load
(``_parse_lib_symbols`` returned ``{}``) and the save path regenerated the
section from the local symbol cache. That lost the exact, as-authored symbol
graphics/pins and dropped any custom symbols not present in the cache.

The library now parses each embedded definition as raw S-expression keyed by
lib_id and re-emits it verbatim, syncing the set on save (preserve used,
generate newly added, prune removed).
"""

import tempfile
from pathlib import Path

import sexpdata

import kicad_sch_api as ksa
from kicad_sch_api.parsers.elements.library_parser import LibraryParser

REF = Path(__file__).parent.parent / "reference_kicad_projects"


def _lib_symbols_block(text: str) -> str:
    """Extract the raw ``(lib_symbols ...)`` block from schematic text."""
    lines = text.splitlines()
    start = end = None
    depth = 0
    for i, line in enumerate(lines):
        if start is None and line.strip().startswith("(lib_symbols"):
            start = i
            depth = line.count("(") - line.count(")")
            continue
        if start is not None:
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                end = i
                break
    return "\n".join(lines[start : end + 1]) if start is not None else ""


# --- Parser-level ---------------------------------------------------------


def _lib_symbols_sexp(*lib_ids):
    parts = [sexpdata.Symbol("lib_symbols")]
    for lib_id in lib_ids:
        parts.append(
            [
                sexpdata.Symbol("symbol"),
                lib_id,
                [sexpdata.Symbol("pin_names"), [sexpdata.Symbol("offset"), 0]],
                [sexpdata.Symbol("in_bom"), sexpdata.Symbol("yes")],
            ]
        )
    return parts


def test_parse_stores_definitions_keyed_by_lib_id():
    parser = LibraryParser()
    result = parser._parse_lib_symbols(_lib_symbols_sexp("Device:R", "Custom:WeirdPart"))
    assert list(result.keys()) == ["Device:R", "Custom:WeirdPart"]
    # Values are the raw symbol S-expressions
    assert str(result["Device:R"][0]) == "symbol"
    assert result["Device:R"][1] == "Device:R"


def test_parse_serialize_roundtrip_is_verbatim():
    parser = LibraryParser()
    src = _lib_symbols_sexp("Device:R", "Custom:WeirdPart")
    parsed = parser._parse_lib_symbols(src)
    out = parser._lib_symbols_to_sexp(parsed)
    # Serialized structure must equal the original (order + content)
    assert out == src


# --- Schematic-level ------------------------------------------------------


def test_loaded_lib_symbols_block_is_byte_identical_after_roundtrip():
    ref = REF / "property_positioning_resistor" / "resistor.kicad_sch"
    sch = ksa.Schematic.load(str(ref))
    assert len(sch._data["lib_symbols"]) >= 1  # embedded def captured

    out = Path(tempfile.mkdtemp()) / "resistor.kicad_sch"
    sch.save(str(out))

    original = _lib_symbols_block(ref.read_text(encoding="utf-8"))
    roundtrip = _lib_symbols_block(out.read_text(encoding="utf-8"))
    assert original and original == roundtrip


def test_removing_last_component_prunes_its_lib_symbol():
    ref = REF / "property_positioning_resistor" / "resistor.kicad_sch"
    sch = ksa.Schematic.load(str(ref))
    # There is exactly one resistor; remove it.
    refs = [c.reference for c in sch.components.all()]
    assert refs, "reference file expected to contain a component"
    sch.components.remove(refs[0])

    out = Path(tempfile.mkdtemp()) / "resistor.kicad_sch"
    sch.save(str(out))

    # No components left -> lib_symbols pruned to empty.
    assert sch._data["lib_symbols"] == {}
