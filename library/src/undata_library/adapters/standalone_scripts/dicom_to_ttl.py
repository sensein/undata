"""Generate a TTL (Turtle) ontology file from pydicom's DICOM data element dictionary.

This creates an OWL-compatible RDF representation of DICOM tags so they can be
loaded into the ontology store and matched against registry elements like
EchoTime, RepetitionTime, FlipAngle, etc.

Usage:
    python dicom_to_ttl.py > dicom.ttl
    # Then: undata-library ontology add --name dicom --url dicom.ttl --format ttl
"""

from __future__ import annotations

import sys
from pathlib import Path


def generate_dicom_ttl(output_path: Path | None = None) -> str:
    """Generate TTL from pydicom's data element dictionary.

    Each DICOM tag becomes a class with:
    - rdfs:label = keyword (e.g., "EchoTime")
    - rdfs:comment = description (e.g., "Echo Time")
    - dicom:tag = tag string (e.g., "(0018,0081)")
    - dicom:vr = value representation (e.g., "DS")
    """
    try:
        from pydicom.datadict import DicomDictionary
    except ImportError:
        raise ImportError("pydicom is required: pip install pydicom")

    lines = [
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix dicom: <http://dicom.nema.org/resources/ontology/DCM/> .",
        "",
        "<http://dicom.nema.org/resources/ontology/DCM> a owl:Ontology ;",
        '    rdfs:label "DICOM Data Element Dictionary" .',
        "",
    ]

    count = 0
    for tag, entry in sorted(DicomDictionary.items()):
        vr, vm, name, is_retired, keyword = entry
        if not keyword or keyword.startswith("_"):
            continue

        # Format tag as (GGGG,EEEE)
        group = (tag >> 16) & 0xFFFF
        element_num = tag & 0xFFFF
        tag_str = f"({group:04X},{element_num:04X})"

        # Escape quotes in name
        safe_name = name.replace('"', '\\"')
        safe_keyword = keyword.replace('"', '\\"')

        uri = f"dicom:{keyword}"
        # Use the human-readable name as primary label for better embedding match
        # Add keyword and tag as synonyms so both forms are searchable
        primary_label = safe_name if safe_name else safe_keyword
        lines.append(f"{uri} a owl:Class ;")
        lines.append(f'    rdfs:label "{primary_label}" ;')
        if safe_name != safe_keyword:
            lines.append(
                f'    <http://www.geneontology.org/formats/oboInOwl#hasExactSynonym> "{safe_keyword}" ;'
            )
        lines.append(
            f'    rdfs:comment "DICOM {tag_str} {safe_name} (keyword: {safe_keyword}, VR: {vr})" ;'
        )
        lines.append(f'    dicom:tag "{tag_str}" ;')
        lines.append(f'    dicom:vr "{vr}" .')
        lines.append("")
        count += 1

    ttl = "\n".join(lines)

    if output_path:
        output_path.write_text(ttl, encoding="utf-8")

    return ttl


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    ttl = generate_dicom_ttl(output)
    if not output:
        print(ttl)
    else:
        print(f"Generated {output}: {ttl.count('a owl:Class')} DICOM tags")
