"""LLM tool definitions for enrichment and ingestion in curation chat.

These tools are called by the LLM during chat-based curation to:
- Suggest ontology annotations for elements
- Suggest units for elements
- Assess alignment between two elements
- Generate descriptions
- Trigger dataset ingestion
"""

from __future__ import annotations

ENRICHMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "suggest_annotation",
            "description": (
                "Suggest an ontology annotation for a data element. "
                "Searches the ontology store (NCIT, DICOM, NIDM, RadLex, PATO) "
                "and proposes the best match with reasoning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_sha256": {
                        "type": "string",
                        "description": "SHA-256 hash (or prefix) of the element",
                    },
                },
                "required": ["entity_sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_unit",
            "description": (
                "Suggest a unit of measurement for a data element "
                "based on its name, description, and context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_sha256": {
                        "type": "string",
                        "description": "SHA-256 hash (or prefix) of the element",
                    },
                },
                "required": ["entity_sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_alignment",
            "description": (
                "Compare two data elements and assess whether they represent "
                "the same concept, related concepts, or different concepts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_a_sha256": {
                        "type": "string",
                        "description": "SHA-256 of the first element",
                    },
                    "element_b_sha256": {
                        "type": "string",
                        "description": "SHA-256 of the second element",
                    },
                },
                "required": ["element_a_sha256", "element_b_sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_description",
            "description": (
                "Generate a concise description for a data element "
                "based on its name, data type, unit, and source context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_sha256": {
                        "type": "string",
                        "description": "SHA-256 hash (or prefix) of the element",
                    },
                },
                "required": ["entity_sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_ingestion",
            "description": (
                "Queue a dataset for ingestion into the registry. "
                "Provide a repository URL and optionally an adapter type."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repository_url": {
                        "type": "string",
                        "description": "URL of the dataset or repository",
                    },
                    "adapter_type": {
                        "type": "string",
                        "description": (
                            "Adapter to use (bids, dandi,"
                            " reproschema, csv, json-schema)"
                        ),
                    },
                },
                "required": ["repository_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "batch_enrich",
            "description": (
                "Run batch LLM enrichment on unannotated elements. Optionally filter by source."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Filter by source (e.g., 'bids', 'nwb')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max elements to process (default 50)",
                    },
                },
                "required": [],
            },
        },
    },
]
