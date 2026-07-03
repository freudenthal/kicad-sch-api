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
from kicad_sch_api.parsers.elements.sheet_parser import SheetParser
from kicad_sch_api.parsers.elements.symbol_parser import SymbolParser
from kicad_sch_api.parsers.elements.wire_parser import WireParser


def _tag(sexp_list):
    return [str(x[0]) for x in sexp_list if isinstance(x, list) and x]


def _parse_symbol(sexp_str):
    return SymbolParser()._parse_symbol(sexpdata.loads(sexp_str))


def _sym_field(out, tag):
    return next((x for x in out if isinstance(x, list) and str(x[0]) == tag), None)


# --- symbol field preservation (mirror / sim flags / lib_name / autoplaced) ---


def _roundtrip_symbol(sexp_str):
    p = SymbolParser()
    return p._symbol_to_sexp(p._parse_symbol(sexpdata.loads(sexp_str)), "root")


def test_mirror_preserved():
    out = _roundtrip_symbol(
        '(symbol (lib_id "Device:C") (at 10 10 0) (mirror x) (unit 1) '
        "(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
        '(uuid "11111111-1111-1111-1111-111111111111"))'
    )
    tags = _tag(out)
    assert "mirror" in tags and tags.index("mirror") == tags.index("at") + 1
    assert str(_sym_field(out, "mirror")[1]) == "x"


def test_mirror_absent_not_emitted():
    out = _roundtrip_symbol(
        '(symbol (lib_id "Device:C") (at 10 10 0) (unit 1) '
        '(uuid "11111111-1111-1111-1111-111111111111"))'
    )
    assert "mirror" not in _tag(out)


def test_exclude_from_sim_and_dnp_preserved():
    out = _roundtrip_symbol(
        '(symbol (lib_id "Device:C") (at 10 10 0) (unit 1) '
        "(exclude_from_sim yes) (in_bom no) (on_board yes) (dnp yes) "
        '(uuid "11111111-1111-1111-1111-111111111111"))'
    )
    assert str(_sym_field(out, "exclude_from_sim")[1]) == "yes"
    assert str(_sym_field(out, "dnp")[1]) == "yes"


def test_lib_name_preserved_before_lib_id():
    out = _roundtrip_symbol(
        '(symbol (lib_name "GND_3") (lib_id "power:GND") (at 10 10 0) (unit 1) '
        '(uuid "11111111-1111-1111-1111-111111111111"))'
    )
    tags = _tag(out)
    assert tags.index("lib_name") < tags.index("lib_id")
    assert _sym_field(out, "lib_name")[1] == "GND_3"


def test_fields_autoplaced_only_emitted_when_true():
    # Present + yes -> emitted
    out_yes = _roundtrip_symbol(
        '(symbol (lib_id "Device:C") (at 10 10 0) (unit 1) (dnp no) '
        '(fields_autoplaced yes) (uuid "11111111-1111-1111-1111-111111111111"))'
    )
    assert "fields_autoplaced" in _tag(out_yes)
    # Absent -> not emitted (KiCAD never writes "no")
    out_absent = _roundtrip_symbol(
        '(symbol (lib_id "Device:C") (at 10 10 0) (unit 1) (dnp no) '
        '(uuid "11111111-1111-1111-1111-111111111111"))'
    )
    assert "fields_autoplaced" not in _tag(out_absent)


# --- sheet preservation ---------------------------------------------------


def test_sheet_property_and_fill_preserved():
    sheet_sexp = sexpdata.loads(
        "(sheet (at 100 100) (size 20 20) "
        "(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0)) "
        '(uuid "22222222-2222-2222-2222-222222222222") '
        '(property "Sheetname" "Sub" (at 100 99 0) (show_name no) '
        "(do_not_autoplace no) (effects (font (size 1.27 1.27)))) "
        '(property "Sheetfile" "sub.kicad_sch" (at 100 121 0) '
        "(effects (font (size 1.27 1.27)))))"
    )
    p = SheetParser()
    out = p._sheet_to_sexp(p._parse_sheet(sheet_sexp), "root")
    fill = _sym_field(out, "fill")
    color = next(x for x in fill if isinstance(x, list) and str(x[0]) == "color")
    assert color[4] == 0 and isinstance(color[4], int)  # not 0.0000
    name_prop = next(
        x for x in out if isinstance(x, list) and str(x[0]) == "property" and x[1] == "Sheetname"
    )
    # KiCAD 10 fields preserved on the property
    assert any(isinstance(e, list) and str(e[0]) == "show_name" for e in name_prop)
    assert any(isinstance(e, list) and str(e[0]) == "do_not_autoplace" for e in name_prop)


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
            {
                "lib_id": "Device:R",
                "position": Point(100.0, 100.0),
                "reference": "R1",
                "value": "1k",
            }
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
