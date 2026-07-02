"""
Symbol library definitions parser for KiCAD schematics.

Handles parsing and serialization of Symbol library definitions.
"""

import logging
from typing import Any, Dict, List, Optional

import sexpdata

from ..base import BaseElementParser

logger = logging.getLogger(__name__)


class LibraryParser(BaseElementParser):
    """Parser for Symbol library definitions."""

    def __init__(self):
        """Initialize library parser."""
        super().__init__("library")

    def _parse_lib_symbols(self, item: List[Any]) -> Dict[str, Any]:
        """Parse the lib_symbols section.

        Stores each embedded symbol definition as its raw S-expression, keyed
        by lib_id, so it can be re-emitted verbatim on save (see
        ``_lib_symbols_to_sexp``, which passes raw lists through unchanged).
        This preserves the exact, as-loaded symbol graphics/pins/properties for
        every KiCAD version instead of regenerating them from the symbol cache.

        Args:
            item: The full ``(lib_symbols (symbol "Device:R" ...) ...)`` sexp.

        Returns:
            Mapping of lib_id -> raw symbol S-expression (insertion order
            matches the file so serialization order is preserved).
        """
        lib_symbols: Dict[str, Any] = {}
        for sub_item in item[1:]:
            if not isinstance(sub_item, list) or len(sub_item) < 2:
                continue
            if not (isinstance(sub_item[0], sexpdata.Symbol) and str(sub_item[0]) == "symbol"):
                continue
            # (symbol "Device:R" ...) -> lib_id is the first argument
            lib_id = sub_item[1]
            if isinstance(lib_id, sexpdata.Symbol):
                lib_id = str(lib_id)
            if isinstance(lib_id, str):
                lib_symbols[lib_id] = sub_item
            else:
                logger.warning(f"Skipping lib_symbols entry with non-string id: {lib_id!r}")
        logger.debug(f"Parsed {len(lib_symbols)} embedded lib_symbols definitions")
        return lib_symbols

    # Conversion methods from internal format to S-expression

    def _lib_symbols_to_sexp(self, lib_symbols: Dict[str, Any]) -> List[Any]:
        """Convert lib_symbols to S-expression."""
        sexp = [sexpdata.Symbol("lib_symbols")]

        # Add each symbol definition
        for symbol_name, symbol_def in lib_symbols.items():
            if isinstance(symbol_def, list):
                # Raw S-expression data from parsed library file - use directly
                sexp.append(symbol_def)
            elif isinstance(symbol_def, dict):
                # Dictionary format - convert to S-expression
                symbol_sexp = self._create_basic_symbol_definition(symbol_name)
                sexp.append(symbol_sexp)

        return sexp

    def _create_basic_symbol_definition(self, lib_id: str) -> List[Any]:
        """Create a basic symbol definition for KiCAD compatibility."""
        symbol_sexp = [sexpdata.Symbol("symbol"), lib_id]

        # Add basic symbol properties
        symbol_sexp.extend(
            [
                [sexpdata.Symbol("pin_numbers"), [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")]],
                [sexpdata.Symbol("pin_names"), [sexpdata.Symbol("offset"), 0]],
                [sexpdata.Symbol("exclude_from_sim"), sexpdata.Symbol("no")],
                [sexpdata.Symbol("in_bom"), sexpdata.Symbol("yes")],
                [sexpdata.Symbol("on_board"), sexpdata.Symbol("yes")],
            ]
        )

        # Add basic properties for the symbol
        if "R" in lib_id:  # Resistor
            symbol_sexp.extend(
                [
                    [
                        sexpdata.Symbol("property"),
                        "Reference",
                        "R",
                        [sexpdata.Symbol("at"), 2.032, 0, 90],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Value",
                        "R",
                        [sexpdata.Symbol("at"), 0, 0, 90],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Footprint",
                        "",
                        [sexpdata.Symbol("at"), -1.778, 0, 90],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                            [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Datasheet",
                        "~",
                        [sexpdata.Symbol("at"), 0, 0, 0],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                            [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")],
                        ],
                    ],
                ]
            )

        elif "C" in lib_id:  # Capacitor
            symbol_sexp.extend(
                [
                    [
                        sexpdata.Symbol("property"),
                        "Reference",
                        "C",
                        [sexpdata.Symbol("at"), 0.635, 2.54, 0],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Value",
                        "C",
                        [sexpdata.Symbol("at"), 0.635, -2.54, 0],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Footprint",
                        "",
                        [sexpdata.Symbol("at"), 0, -1.27, 0],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                            [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")],
                        ],
                    ],
                    [
                        sexpdata.Symbol("property"),
                        "Datasheet",
                        "~",
                        [sexpdata.Symbol("at"), 0, 0, 0],
                        [
                            sexpdata.Symbol("effects"),
                            [sexpdata.Symbol("font"), [sexpdata.Symbol("size"), 1.27, 1.27]],
                            [sexpdata.Symbol("hide"), sexpdata.Symbol("yes")],
                        ],
                    ],
                ]
            )

        # Add basic graphics and pins (minimal for now)
        symbol_sexp.append([sexpdata.Symbol("embedded_fonts"), sexpdata.Symbol("no")])

        return symbol_sexp
