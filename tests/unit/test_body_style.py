"""Round-trip tests for the KiCAD 10 ``body_style`` symbol field.

KiCAD 10 (schema 20260306+) emits ``(body_style N)`` on every placed symbol to
record the DeMorgan / alternate body representation. Earlier KiCAD versions omit
it entirely. These tests verify that:

1. ``body_style`` is parsed and re-serialized (pass-through) when present.
2. It is emitted in the correct position (immediately after ``unit``).
3. It is NOT added to symbols that never had it (KiCAD 8/9 stay byte-clean).
"""

import sexpdata

from kicad_sch_api.parsers.elements.symbol_parser import SymbolParser


def _placed_symbol_sexp(include_body_style: bool):
    """Build a minimal placed-symbol S-expression, with/without body_style."""
    parts = [
        sexpdata.Symbol("symbol"),
        [sexpdata.Symbol("lib_id"), "Device:R"],
        [sexpdata.Symbol("at"), 100, 100, 0],
        [sexpdata.Symbol("unit"), 1],
    ]
    if include_body_style:
        parts.append([sexpdata.Symbol("body_style"), 1])
    parts += [
        [sexpdata.Symbol("in_bom"), sexpdata.Symbol("yes")],
        [sexpdata.Symbol("on_board"), sexpdata.Symbol("yes")],
        [sexpdata.Symbol("uuid"), "11111111-1111-1111-1111-111111111111"],
    ]
    return parts


def test_body_style_parsed_when_present():
    parser = SymbolParser()
    data = parser._parse_symbol(_placed_symbol_sexp(include_body_style=True))
    assert data["body_style"] == 1


def test_body_style_none_when_absent():
    parser = SymbolParser()
    data = parser._parse_symbol(_placed_symbol_sexp(include_body_style=False))
    assert data["body_style"] is None


def test_body_style_roundtrips_when_present():
    parser = SymbolParser()
    data = parser._parse_symbol(_placed_symbol_sexp(include_body_style=True))
    out = parser._symbol_to_sexp(data, "dummy-schematic-uuid")
    keys = [str(x[0]) for x in out if isinstance(x, list) and x]
    assert "body_style" in keys
    # Must appear immediately after unit (KiCAD 10 ordering)
    assert keys.index("body_style") == keys.index("unit") + 1
    body = next(x for x in out if isinstance(x, list) and str(x[0]) == "body_style")
    assert body[1] == 1


def test_body_style_not_emitted_when_absent():
    """KiCAD 8/9 symbols (no body_style) must not gain the field on save."""
    parser = SymbolParser()
    data = parser._parse_symbol(_placed_symbol_sexp(include_body_style=False))
    out = parser._symbol_to_sexp(data, "dummy-schematic-uuid")
    keys = [str(x[0]) for x in out if isinstance(x, list) and x]
    assert "body_style" not in keys


def test_body_style_survives_schematic_symbol_dataclass():
    """The SchematicSymbol dataclass must carry body_style through **splat."""
    from kicad_sch_api.core.types import SchematicSymbol

    parser = SymbolParser()
    data = parser._parse_symbol(_placed_symbol_sexp(include_body_style=True))
    # Mirror Schematic.__init__: SchematicSymbol(**comp)
    sym = SchematicSymbol(**data)
    assert sym.body_style == 1
