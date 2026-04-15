"""LLM chat service with tool execution for curation assistant."""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator

logger = logging.getLogger(__name__)


def _get_model() -> str:
    """Get the LLM model to use. Supports OLLAMA_HOST for local dev."""
    if os.environ.get("UNDATA_LLM_MODEL"):
        return os.environ["UNDATA_LLM_MODEL"]
    if os.environ.get("OLLAMA_HOST"):
        return "ollama_chat/qwen3.5"
    return "gpt-4.1-mini"


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "propose_entity_change",
            "description": "Propose a change to an entity field. Returns diff preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["elements", "schemas", "values", "valuesets"],
                    },
                    "sha256": {
                        "type": "string",
                        "description": "Entity identifier (sha256 prefix)",
                    },
                    "field": {
                        "type": "string",
                        "description": "Field to change (e.g., unit, description)",
                    },
                    "value": {"description": "New value for the field"},
                },
                "required": ["entity_type", "sha256", "field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_ontology_term",
            "description": (
                "Search the ontology store for a term. Use this instead of guessing URIs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "ontology": {
                        "type": "string",
                        "description": "Optional: restrict to ontology (ncit, uberon, pato, etc.)",
                    },
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_entity",
            "description": "Load an entity's full details for context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["elements", "schemas", "values", "valuesets"],
                    },
                    "sha256": {"type": "string"},
                },
                "required": ["entity_type", "sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_ingestion",
            "description": "Trigger pipeline ingestion for a new source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_url": {"type": "string"},
                    "adapter_pattern": {
                        "type": "string",
                        "enum": [
                            "bids",
                            "nwb",
                            "dandi",
                            "openminds",
                            "aind",
                            "json-schema",
                            "linkml",
                        ],
                    },
                },
                "required": ["source_url", "adapter_pattern"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a curation assistant for the undata data element registry.
Help curators review, edit, and improve entity metadata (elements, schemas, values, valuesets).

Rules:
- Always use lookup_ontology_term to find valid ontology URIs. Never guess or hallucinate URIs.
- Propose changes via propose_entity_change. Never output raw JSON for the user to copy.
- Use fetch_entity to load entity details when needed.
- When asked to ingest a new source, use trigger_ingestion.
- Be concise and helpful. Explain your reasoning."""


async def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    from src.tools.entity_tools import fetch_entity, propose_entity_change
    from src.tools.ontology_tools import lookup_ontology_term
    from src.tools.pipeline_tools import trigger_ingestion

    tool_map = {
        "propose_entity_change": propose_entity_change,
        "lookup_ontology_term": lookup_ontology_term,
        "fetch_entity": fetch_entity,
        "trigger_ingestion": trigger_ingestion,
    }

    func = tool_map.get(name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        result = await func(**arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return json.dumps({"error": str(e)})


async def chat_completion(
    messages: list[dict],
    entity_context: dict | None = None,
) -> AsyncIterator[dict]:
    """Stream a chat completion with tool execution.

    Yields events: {type: "text", content: str} or {type: "tool_call", name: str, result: dict}
    """
    import litellm

    # Build system message with entity context
    system = SYSTEM_PROMPT
    if entity_context:
        ctx = json.dumps(entity_context, indent=2, default=str)
        system += f"\n\nCurrent entity context:\n```json\n{ctx}\n```"

    full_messages = [{"role": "system", "content": system}] + messages

    # Call LLM with tools
    try:
        model = _get_model()
        kwargs: dict = {
            "model": model,
            "messages": full_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "stream": False,
        }
        # Ollama config: explicit API base + disable thinking mode
        if "ollama" in model:
            if os.environ.get("OLLAMA_HOST"):
                kwargs["api_base"] = os.environ["OLLAMA_HOST"]
            kwargs["extra_body"] = {"options": {"num_predict": 2048}, "think": False}
            kwargs["reasoning_effort"] = "none"
            litellm.drop_params = True
        response = await litellm.acompletion(**kwargs)
    except Exception as e:
        yield {"type": "text", "content": f"Error calling LLM: {e}"}
        return

    choice = response.choices[0]
    message = choice.message

    # Handle tool calls
    if message.tool_calls:
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_call", "name": name, "arguments": args, "status": "executing"}

            result_str = await execute_tool(name, args)
            result = json.loads(result_str)

            yield {"type": "tool_result", "name": name, "result": result}

            # Add tool result to messages and get follow-up response
            full_messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            full_messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_str}
            )

        # Get final response after tool execution
        try:
            follow_kwargs: dict = {
                "model": model,
                "messages": full_messages,
                "stream": False,
            }
            if "ollama" in model and os.environ.get("OLLAMA_HOST"):
                follow_kwargs["api_base"] = os.environ["OLLAMA_HOST"]
                follow_kwargs["extra_body"] = {"options": {"num_predict": 2048}, "think": False}
                follow_kwargs["reasoning_effort"] = "none"
            follow_up = await litellm.acompletion(**follow_kwargs)
            yield {"type": "text", "content": follow_up.choices[0].message.content or ""}
        except Exception as e:
            yield {"type": "text", "content": f"Error in follow-up: {e}"}
    else:
        # No tool calls — just text response
        yield {"type": "text", "content": message.content or ""}


AUTO_SUGGEST_PROMPT = """Analyze this entity and suggest improvements. Check for:
1. Missing or incorrect ontology annotations — use lookup_ontology_term to find proper matches
2. Missing or incorrect units — suggest the correct unit and QUDT URI if applicable
3. Description quality — suggest improvements if the description is vague or missing
4. Data type accuracy — check if the data_type matches the actual content

Be specific and actionable. Use propose_entity_change for each suggestion."""


def build_auto_suggest_messages(entity_context: dict) -> list[dict]:
    """Build the message list for auto-suggest on entity load."""
    return [{"role": "user", "content": AUTO_SUGGEST_PROMPT}]
