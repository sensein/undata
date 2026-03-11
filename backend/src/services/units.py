"""UnitResolutionService — cmixf validation + QUDT ontology lookup.

Singleton lifecycle: initialized once in main.py lifespan at startup and stored
in app.state.unit_service. Each element create/update calls resolve() non-blocking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.logging import get_logger

logger = get_logger(__name__)

# ASCII → QUDT local name overrides for cmixf↔QUDT Unicode mismatches
SYMBOL_OVERRIDES: dict[str, str] = {
    "oC": "DEG_C",   # ASCII Celsius → QUDT DEG_C
    "Ohm": "OHM",    # ASCII Ohm → QUDT OHM
    "o": "DEG",      # angle degree (not OCTET)
    "bit": "BIT",
}

QUDT_BASE = "http://qudt.org/vocab/unit/"


def _build_cmixf_validator() -> re.Pattern:
    """Build a regex pattern from the cmixf symbol lists for validation.

    cmixf-12 defines: valid_symbol = [prefix?][base_symbol]
    where base symbols and prefixes come from the cmixf.parser module.
    """
    try:
        import cmixf.parser as cp

        def flatten(lst: list) -> list[str]:
            result: list[str] = []
            for item in lst:
                if isinstance(item, list):
                    result.extend(item)
                else:
                    result.append(str(item))
            return result

        all_base = flatten(cp.unit_b_symbol) + flatten(cp.unit_n_symbol) + flatten(cp.unit_p_symbol)
        all_prefix = (
            flatten(cp.decimal_multiple_prefix)
            + flatten(cp.decimal_submultiple_prefix)
            + flatten(cp.binary_prefix)
        )

        # Sort longest-first for correct alternation matching
        base_pat = "|".join(re.escape(b) for b in sorted(all_base, key=len, reverse=True))
        prefix_pat = "|".join(re.escape(p) for p in sorted(all_prefix, key=len, reverse=True))

        pattern = r"^(?:(?:" + prefix_pat + r")?(?:" + base_pat + r"))$"
        return re.compile(pattern)
    except Exception as exc:
        logger.warning("cmixf.validator.build.failed", extra={"error": str(exc)})
        return re.compile(r"^$")  # reject everything if cmixf not available


# Module-level compiled validator (built once at import time)
_CMIXF_PATTERN: re.Pattern | None = None


def _validate_cmixf(symbol: str) -> bool:
    """Return True if symbol matches the cmixf-12 symbol grammar."""
    global _CMIXF_PATTERN
    if _CMIXF_PATTERN is None:
        _CMIXF_PATTERN = _build_cmixf_validator()
    return bool(_CMIXF_PATTERN.match(symbol))


@dataclass
class UnitResolutionResult:
    qudt_uri: str | None        # None if unresolvable
    qudt_unresolvable: bool     # True only if resolution was attempted but failed
    cmixf_valid: bool | None    # None if no symbol given


class UnitResolutionService:
    """Singleton service for unit symbol validation and QUDT URI resolution.

    At startup, loads QUDT TTL from *ttl_path* and builds three lookup dicts:
      - by_ucum_code:  UCUM code string  → QUDT URI
      - by_symbol:     symbol (lowercased) → QUDT URI
      - by_label:      rdfs:label (lowercased) → QUDT URI

    Resolution is multi-pass:
      1. SYMBOL_OVERRIDES[symbol]  → QUDT local name
      2. by_ucum_code[symbol]
      3. by_symbol[symbol.lower()]
      4. by_label[label.lower()]
    """

    def __init__(self, ttl_path: str) -> None:
        self.by_ucum_code: dict[str, str] = {}
        self.by_symbol: dict[str, str] = {}
        self.by_label: dict[str, str] = {}
        self._all_units: list[dict] = []
        self._load(ttl_path)

    def _load(self, ttl_path: str) -> None:
        """Parse TTL and build lookup indexes (~100ms at startup)."""
        try:
            import rdflib
            from rdflib.namespace import RDF, RDFS

            QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")

            g = rdflib.Graph()
            g.parse(ttl_path, format="turtle")
            logger.info("qudt.ttl.loaded", extra={"path": ttl_path, "triples": len(g)})

            for subj in g.subjects(RDF.type, QUDT.Unit):
                uri = str(subj)
                local_name = str(subj).split("/")[-1]

                # Collect labels
                labels = [
                    str(o)
                    for o in g.objects(subj, RDFS.label)
                    if isinstance(o, rdflib.Literal)
                ]

                # Collect UCUM codes
                ucum_codes = [
                    str(o)
                    for o in g.objects(subj, QUDT.ucumCode)
                    if isinstance(o, rdflib.Literal)
                ]

                # Collect symbols
                symbols = [
                    str(o)
                    for o in g.objects(subj, QUDT.symbol)
                    if isinstance(o, rdflib.Literal)
                ]

                for code in ucum_codes:
                    if code and code not in self.by_ucum_code:
                        self.by_ucum_code[code] = uri

                for sym in symbols:
                    if sym:
                        key = sym.lower()
                        if key not in self.by_symbol:
                            self.by_symbol[key] = uri

                for lbl in labels:
                    if lbl:
                        key = lbl.lower()
                        if key not in self.by_label:
                            self.by_label[key] = uri

                # Store for list_known()
                self._all_units.append(
                    {
                        "label": labels[0] if labels else local_name,
                        "symbol": symbols[0] if symbols else None,
                        "qudt_uri": uri,
                    }
                )

            logger.info(
                "qudt.index.built",
                extra={
                    "units": len(self._all_units),
                    "ucum_codes": len(self.by_ucum_code),
                    "symbols": len(self.by_symbol),
                    "labels": len(self.by_label),
                },
            )
        except Exception as exc:
            logger.error("qudt.load.failed", extra={"error": str(exc)})
            # Service degrades gracefully — all lookups return unresolvable

    def resolve(self, label: str | None, symbol: str | None) -> UnitResolutionResult:
        """Resolve a unit to its QUDT URI and validate its cmixf symbol.

        Resolution is non-blocking: always returns a result even if unresolvable.
        """
        cmixf_valid: bool | None = None
        qudt_uri: str | None = None

        # --- cmixf validation ---
        if symbol is not None:
            cmixf_valid = _validate_cmixf(symbol)

        # --- QUDT resolution ---
        if symbol is not None:
            # Pass 1: SYMBOL_OVERRIDES
            if symbol in SYMBOL_OVERRIDES:
                qudt_uri = QUDT_BASE + SYMBOL_OVERRIDES[symbol]

            # Pass 2: UCUM code exact match
            if qudt_uri is None:
                qudt_uri = self.by_ucum_code.get(symbol)

            # Pass 3: symbol map (case-insensitive)
            if qudt_uri is None:
                qudt_uri = self.by_symbol.get(symbol.lower())

        # Pass 4: label map (case-insensitive)
        if qudt_uri is None and label is not None:
            qudt_uri = self.by_label.get(label.lower())

        # Determine unresolvable flag:
        # Only True when we had something to look up but couldn't find it
        attempted = symbol is not None or label is not None
        qudt_unresolvable = attempted and qudt_uri is None

        return UnitResolutionResult(
            qudt_uri=qudt_uri,
            qudt_unresolvable=qudt_unresolvable,
            cmixf_valid=cmixf_valid,
        )

    def list_known(self) -> list[dict]:
        """Return all QUDT units loaded from the bundled TTL."""
        return self._all_units
