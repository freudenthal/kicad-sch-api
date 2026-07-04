#!/usr/bin/env python3
"""Reference-format validation (Stage 17.3, G1).

KiCad 10 accepts lowercase letters in a reference prefix (e.g. "Rf1" for a
feedback resistor); the GUI allows them and kicad-cli processes such a schematic
without complaint. Validate-on-save must therefore not be stricter than KiCad --
the old pattern rejected "Rf1" and aborted circuit-synth's update-mode
regeneration. These tests pin the widened pattern, the verbose ValidationError,
and a lowercase-ref save round-trip.
"""

from pathlib import Path

import pytest

import kicad_sch_api as ksa
from kicad_sch_api.core.exceptions import ValidationError
from kicad_sch_api.utils.validation import (
    SchematicValidator,
    ValidationIssue,
    ValidationLevel,
)

# A resistor schematic manually created in KiCad; loading it needs no symbol-library
# resolution (it carries embedded lib_symbols), so this round-trip is robust to the
# suite's pre-existing symbol-cache pollution.
_REF_RESISTOR = (
    Path(__file__).parent
    / "reference_kicad_projects"
    / "property_positioning_resistor"
    / "resistor.kicad_sch"
)


@pytest.fixture
def validator():
    return SchematicValidator()


@pytest.mark.parametrize(
    "ref",
    ["R1", "U5", "#PWR01", "#FLG01", "Rf1", "Cf1", "Cin2", "U?", "R", "Rf"],
)
def test_valid_references(validator, ref):
    assert validator.validate_reference(ref) is True, ref


@pytest.mark.parametrize("ref", ["", "1R", "R 1", "R-1", "123"])
def test_invalid_references(validator, ref):
    assert validator.validate_reference(ref) is False, ref


def test_validation_error_str_names_offending_issues():
    err = ValidationError(
        "Cannot save schematic with validation errors",
        issues=[
            ValidationIssue(
                category="reference",
                message="Invalid reference format: Rf1",
                level=ValidationLevel.ERROR,
            )
        ],
    )
    text = str(err)
    assert "Cannot save schematic with validation errors" in text
    assert "Rf1" in text


def test_validation_error_str_truncates_many_issues():
    issues = [
        ValidationIssue(
            category="reference",
            message=f"bad ref {i}",
            level=ValidationLevel.ERROR,
        )
        for i in range(8)
    ]
    err = ValidationError("boom", issues=issues)
    text = str(err)
    assert "bad ref 0" in text
    assert "+3 more" in text


def test_lowercase_prefix_reference_round_trip(tmp_path):
    """A component renamed to a lowercase-prefix ref survives save + reload."""
    sch = ksa.load_schematic(str(_REF_RESISTOR))
    comp = next(iter(sch.components))
    comp.reference = "Rf9"

    out = tmp_path / "reftest.kicad_sch"
    sch.save(str(out))  # previously raised ValidationError on "Rf9"

    reloaded = ksa.load_schematic(str(out))
    refs = {str(c.reference) for c in reloaded.components}
    assert "Rf9" in refs, refs
