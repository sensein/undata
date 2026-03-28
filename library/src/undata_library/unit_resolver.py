"""QUDT unit resolution — resolves raw unit strings to canonical QUDT URIs.

Loads QUDT vocabulary into the OntologyStore (pyoxigraph) and provides
a thin resolution layer with an alias table for common neuroscience units.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pyoxigraph

logger = logging.getLogger(__name__)

# QUDT namespace prefixes
QUDT_UNIT_NS = "http://qudt.org/vocab/unit/"
QUDT_NS = "http://qudt.org/schema/qudt/"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"

# Common neuroscience unit aliases → QUDT local names
UNIT_ALIASES: dict[str, str] = {
    # Time
    "years": "YR",
    "year": "YR",
    "yr": "YR",
    "months": "MO",
    "month": "MO",
    "mo": "MO",
    "days": "DAY",
    "day": "DAY",
    "d": "DAY",
    "hours": "HR",
    "hour": "HR",
    "hr": "HR",
    "h": "HR",
    "seconds": "SEC",
    "second": "SEC",
    "sec": "SEC",
    "s": "SEC",
    "milliseconds": "MilliSEC",
    "millisecond": "MilliSEC",
    "ms": "MilliSEC",
    "microseconds": "MicroSEC",
    "microsecond": "MicroSEC",
    "us": "MicroSEC",
    # Mass
    "kilogram": "KiloGM",
    "kilograms": "KiloGM",
    "kg": "KiloGM",
    "gram": "GM",
    "grams": "GM",
    "g": "GM",
    "milligram": "MilliGM",
    "mg": "MilliGM",
    "pound": "LB",
    "pounds": "LB",
    "lb": "LB",
    "lbs": "LB",
    # Length
    "meter": "M",
    "meters": "M",
    "m": "M",
    "centimeter": "CentiM",
    "centimeters": "CentiM",
    "cm": "CentiM",
    "millimeter": "MilliM",
    "millimeters": "MilliM",
    "mm": "MilliM",
    "micrometer": "MicroM",
    "micrometers": "MicroM",
    "um": "MicroM",
    # Electrical
    "volt": "V",
    "volts": "V",
    "millivolt": "MilliV",
    "millivolts": "MilliV",
    "mv": "MilliV",
    "microvolt": "MicroV",
    "microvolts": "MicroV",
    "uv": "MicroV",
    "ampere": "A",
    "amp": "A",
    "ohm": "OHM",
    # Frequency
    "hertz": "HZ",
    "hz": "HZ",
    "kilohertz": "KiloHZ",
    "khz": "KiloHZ",
    # Temperature
    "celsius": "DEG_C",
    "fahrenheit": "DEG_F",
    "kelvin": "K",
    # Pressure
    "pascal": "PA",
    "pa": "PA",
    "mmhg": "MilliM_HG",
    # Percentage
    "percent": "PERCENT",
    "%": "PERCENT",
}


@dataclass
class UnitResult:
    """Result of resolving a unit string."""

    uri: str
    label: str
    symbol: str | None = None
    conversion_multiplier: float | None = None
    conversion_offset: float | None = None


class UnitResolver:
    """Resolves raw unit strings to canonical QUDT URIs.

    Uses a combination of:
    1. Alias table for common neuroscience variants
    2. QUDT symbol/label lookup via pyoxigraph
    """

    def __init__(self, qudt_path: Path | None = None) -> None:
        self._store = pyoxigraph.Store()
        self._symbol_index: dict[str, str] = {}  # lowercase symbol → QUDT URI
        self._label_index: dict[str, str] = {}  # lowercase label → QUDT URI
        self._unit_data: dict[str, dict] = {}  # URI → {label, symbol, multiplier, offset}

        if qudt_path is None:
            qudt_path = Path(__file__).parent / "data" / "qudt" / "VOCAB_QUDT-UNITS-ALL.ttl"

        if qudt_path.exists():
            self._load_qudt(qudt_path)
        else:
            logger.warning("QUDT vocabulary not found at %s", qudt_path)

    def _load_qudt(self, path: Path) -> None:
        """Load QUDT TTL and build lookup indices."""
        try:
            self._store.load(
                path.read_bytes(),
                "text/turtle",
                base_iri="http://qudt.org/vocab/unit/",
            )
        except Exception as e:
            logger.warning("Failed to load QUDT: %s", e)
            return

        # Build indices from the store
        symbol_pred = pyoxigraph.NamedNode(f"{QUDT_NS}symbol")
        ucum_pred = pyoxigraph.NamedNode(f"{QUDT_NS}ucumCode")
        label_pred = pyoxigraph.NamedNode(f"{RDFS_NS}label")
        mult_pred = pyoxigraph.NamedNode(f"{QUDT_NS}conversionMultiplier")
        offset_pred = pyoxigraph.NamedNode(f"{QUDT_NS}conversionOffset")

        # Index symbols
        for quad in self._store.quads_for_pattern(None, symbol_pred, None, None):
            uri = str(quad.subject.value)
            sym = str(quad.object.value).strip()
            if sym:
                self._symbol_index[sym.lower()] = uri
                self._unit_data.setdefault(uri, {})["symbol"] = sym

        # Index UCUM codes
        for quad in self._store.quads_for_pattern(None, ucum_pred, None, None):
            uri = str(quad.subject.value)
            code = str(quad.object.value).strip()
            if code:
                self._symbol_index[code.lower()] = uri

        # Index labels
        for quad in self._store.quads_for_pattern(None, label_pred, None, None):
            uri = str(quad.subject.value)
            lbl = str(quad.object.value).strip()
            if lbl and uri.startswith(QUDT_UNIT_NS):
                self._label_index[lbl.lower()] = uri
                self._unit_data.setdefault(uri, {})["label"] = lbl

        # Index conversion multipliers
        for quad in self._store.quads_for_pattern(None, mult_pred, None, None):
            uri = str(quad.subject.value)
            try:
                val = float(str(quad.object.value))
                self._unit_data.setdefault(uri, {})["multiplier"] = val
            except (ValueError, TypeError):
                pass

        # Index conversion offsets
        for quad in self._store.quads_for_pattern(None, offset_pred, None, None):
            uri = str(quad.subject.value)
            try:
                val = float(str(quad.object.value))
                self._unit_data.setdefault(uri, {})["offset"] = val
            except (ValueError, TypeError):
                pass

        logger.info("QUDT loaded: %d symbols, %d labels", len(self._symbol_index), len(self._label_index))

    def resolve(self, raw: str | None) -> UnitResult | None:
        """Resolve a raw unit string to a QUDT URI.

        Resolution order:
        1. Alias table (common neuroscience variants)
        2. Symbol/UCUM code lookup in QUDT
        3. Label lookup in QUDT
        """
        if not raw or not raw.strip():
            return None

        raw_lower = raw.strip().lower()

        # 1. Check alias table
        if raw_lower in UNIT_ALIASES:
            local_name = UNIT_ALIASES[raw_lower]
            uri = f"{QUDT_UNIT_NS}{local_name}"
            data = self._unit_data.get(uri, {})
            return UnitResult(
                uri=uri,
                label=data.get("label", local_name),
                symbol=data.get("symbol"),
                conversion_multiplier=data.get("multiplier"),
                conversion_offset=data.get("offset"),
            )

        # 2. Symbol/UCUM lookup
        if raw_lower in self._symbol_index:
            uri = self._symbol_index[raw_lower]
            data = self._unit_data.get(uri, {})
            return UnitResult(
                uri=uri,
                label=data.get("label", ""),
                symbol=data.get("symbol"),
                conversion_multiplier=data.get("multiplier"),
                conversion_offset=data.get("offset"),
            )

        # 3. Label lookup
        if raw_lower in self._label_index:
            uri = self._label_index[raw_lower]
            data = self._unit_data.get(uri, {})
            return UnitResult(
                uri=uri,
                label=data.get("label", ""),
                symbol=data.get("symbol"),
                conversion_multiplier=data.get("multiplier"),
                conversion_offset=data.get("offset"),
            )

        return None

    def conversion_factor(self, uri_a: str, uri_b: str) -> float | None:
        """Compute conversion factor from unit A to unit B.

        Uses QUDT conversionMultiplier values:
        factor = multiplier_a / multiplier_b

        Returns None if either unit lacks a conversion multiplier.
        """
        data_a = self._unit_data.get(uri_a, {})
        data_b = self._unit_data.get(uri_b, {})

        mult_a = data_a.get("multiplier")
        mult_b = data_b.get("multiplier")

        if mult_a is None or mult_b is None or mult_b == 0:
            return None

        return mult_a / mult_b

    def unit_count(self) -> int:
        """Number of indexed unit symbols + labels."""
        return len(self._symbol_index) + len(self._label_index)

    def validate_cmixf(self, unit_string: str) -> dict:
        """Validate a unit string against the cmixf grammar.

        Returns: {valid: bool, error: str | None}
        """
        try:
            import cmixf

            cmixf.parse(unit_string)
            return {"valid": True, "error": None}
        except ImportError:
            return {"valid": True, "error": "cmixf not available"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
