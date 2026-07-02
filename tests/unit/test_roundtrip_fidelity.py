"""Round-trip fidelity tests for the symbol/element serializers.

These cover regressions that previously caused large diffs when re-saving an
unmodified KiCAD schematic:

- symbol instances grouped under one (project ...) block per project
- KiCAD 10 hidden-property flag not duplicated
- in_pos_files pass-through
- junction diameter / label rotation whole-number formatting
- top-level sections emitted in KiCAD's canonical order
"""

import sexpdata

from kicad_sch_api.core.parser import SExpressionParser
from kicad_sch_api.core.types import Point, SymbolInstance
from kicad_sch_api.parsers.elements.label_parser import LabelParser
from kicad_sch_api.parsers.elements.symbol_parser import SymbolParser
from kicad_sch_api.parsers.elements.wire_parser import WireParser


def _tag(sexp_list):
    return [str(x[0]) for x in sexp_list if isinstance(x, list) and x]


# --- instances grouping ---------------------------------------------------


def test_instances_grouped_by_project():
    parser = SymbolParser()
    symbol_data = {
        "lib_id": "Device:C",
        "position": Point(100.0, 100.0),
        "reference": "C1",
        "instances": [
            SymbolInstance(path="/root/a", reference="C1", unit=1, project="Board"),
            SymbolInstance(path="/root/b", reference="C2", unit=1, project="Board"),
            SymbolInstance(path="/root/c", reference="C3", unit=1, project="Board"),
        ],
    }
    out = parser._symbol_to_sexp(symbol_data, "root")
    instances = next(x for x in out if isinstance(x, list) and str(x[0]) == "instances")
    projects = [x for x in instances[1:] if str(x[0]) == "project"]
    assert len(projects) == 1, "all paths for one project must share a single (project ...) block"
    paths = [x for x in projects[0][2:] if str(x[0]) == "path"]
    assert len(paths) == 3


# --- KiCAD 10 hide flag ---------------------------------------------------


def _kicad10_hidden_property():
    # (property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
    return [
        sexpdata.Symbol("property"),
        "Datasheet",
        "",
        [sexpdata.Symbol("at"), 0, 0, 0],
        [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")],
        [
            sexpdata.Symbol("effects"),
            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
        ],
    ]


def test_kicad10_direct_child_hide_not_duplicated():
    parser = SymbolParser()
    prop = _kicad10_hidden_property()
    updated = parser._update_property_hide_flag(prop, should_hide=True)
    # No duplicate: exactly one hide in the whole property (the direct child),
    # and none injected into effects.
    direct = [x for x in updated if isinstance(x, list) and str(x[0]) == "hide"]
    effects = next(x for x in updated if isinstance(x, list) and str(x[0]) == "effects")
    nested = [x for x in effects if isinstance(x, list) and str(x[0]) == "hide"]
    assert len(direct) == 1
    assert len(nested) == 0
    assert updated == prop  # unchanged -> byte-perfect round-trip


def test_parse_detects_direct_child_hide():
    parser = SymbolParser()
    parsed = parser._parse_property(_kicad10_hidden_property())
    assert parsed["hidden"] is True


# --- number formatting ----------------------------------------------------


def test_junction_zero_diameter_is_integer():
    parser = WireParser()
    sexp = parser._junction_to_sexp({"position": {"x": 10.0, "y": 20.0}, "diameter": 0.0})
    diameter = next(x for x in sexp if isinstance(x, list) and str(x[0]) == "diameter")
    assert diameter[1] == 0 and isinstance(diameter[1], int)


def test_hierarchical_label_zero_rotation_is_integer():
    parser = LabelParser()
    sexp = parser._hierarchical_label_to_sexp(
        {"text": "NET", "position": {"x": 10.0, "y": 20.0}, "rotation": 0.0, "justify": "right"}
    )
    at = next(x for x in sexp if isinstance(x, list) and str(x[0]) == "at")
    assert at[3] == 0 and isinstance(at[3], int)
    # justify preserved through the serializer
    effects = next(x for x in sexp if isinstance(x, list) and str(x[0]) == "effects")
    justify = next(x for x in effects if isinstance(x, list) and str(x[0]) == "justify")
    assert str(justify[1]) == "right"


# --- section ordering -----------------------------------------------------


def test_sections_emitted_in_kicad_order():
    parser = SExpressionParser()
    data = {
        "version": 20250114,
        "generator": "eeschema",
        "uuid": "u",
        "paper": "A4",
        "lib_symbols": {},
        "components": [
            {"lib_id": "Device:R", "position": Point(100.0, 100.0), "reference": "R1", "value": "1k"}
        ],
        "wires": [{"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}], "uuid": "w"}],
        "junctions": [{"position": {"x": 0, "y": 0}, "uuid": "j"}],
        "hierarchical_labels": [
            {"text": "H", "position": {"x": 0, "y": 0}, "rotation": 0, "justify": "left"}
        ],
    }
    out = parser._schematic_data_to_sexp(data)
    tags = _tag(out)
    # junction before wire before hierarchical_label before symbol
    assert tags.index("junction") < tags.index("wire")
    assert tags.index("wire") < tags.index("hierarchical_label")
    assert tags.index("hierarchical_label") < tags.index("symbol")
