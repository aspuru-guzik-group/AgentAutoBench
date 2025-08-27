from extract_context import extract_action_trace
import json, re, inspect
from datetime import datetime


def extract_action_trace_json(session_name: str,
                              include_agents=None,
                              include_tools=None,
                              drop_empty: bool = True,
                              trim_output: int = 8000,
                              pretty: bool = True,
                              filepath: str | None = None):
    """
    Exports a filtered agent action trace to JSON (optionally saving to a file).

    Uses `extract_action_trace(session_name)` to build the raw trace, then
    applies post-filters:
      • Keep steps only from selected agents (`include_agents`) and/or
        steps that called selected tools (`include_tools`).
      • Optionally drop steps that become empty after tool filtering (`drop_empty`).
      • Truncate long string tool outputs to `trim_output` characters.
      • Pretty-print JSON (`pretty`) and optionally write it to `filepath`.

    Args:
        session_name (str): Session suffix used to fetch the raw trace.
        include_agents (Iterable[str] | None): If provided, only steps whose
            `agent` is in this set are retained. Matching is case-sensitive.
        include_tools (Iterable[str] | None): If provided, only tool-call entries
            whose `tool_name` is in this set are kept; a step is kept if it
            contains at least one such call (or its agent is explicitly included).
        drop_empty (bool): When `include_tools` is set, drop steps that have no
            remaining tool calls after filtering and are not explicitly included
            by `include_agents`. Default: True.
        trim_output (int): Maximum length for string-valued tool outputs; longer
            strings are truncated and suffixed with " …[truncated]". Default: 8000.
        pretty (bool): If True, JSON is indented with 2 spaces; otherwise
            a compact representation is produced. Default: True.
        filepath (str | None): If provided, the JSON text is written to this path
            using UTF-8 encoding. Directories must already exist.

    Returns:
        str: The JSON-encoded text of the filtered action trace (always returned,
            regardless of whether `filepath` is given).

    Raises:
        Exception: Any exception propagated from `extract_action_trace` (e.g.,
            database access issues).
        OSError: If writing to `filepath` fails (e.g., missing directory, permission).
        TypeError: If JSON serialization fails for unexpected object types
            (unlikely because `default=str` is used).

    """
    include_agents = set(include_agents or [])
    include_tools  = set(include_tools or [])

    raw = extract_action_trace(session_name)  # uses your existing function

    # post-filter
    def _post_filter(data):
    """
    Filters an agent trace by agent/tool and trims long tool outputs.

    A step is **kept** if:
      • `include_agents` is non-empty and the step's `agent` is in it, OR
      • `include_tools` is non-empty and the step used at least one tool whose
        `tool_name` is in `include_tools`, OR
      • both `include_agents` and `include_tools` are empty (keep everything).

    For each kept step:
      • If `include_tools` is provided, `tool_calls` are filtered to those tools only.
      • Any string `output` longer than `trim_output` characters is truncated and
        suffixed with `" …[truncated]"`.
      • If `drop_empty` is True **and** `include_tools` is provided, steps that end up
        with no remaining `tool_calls` are dropped unless their `agent` was explicitly
        included via `include_agents`.

    The input dict is not mutated; a shallow copy is returned with a rewritten
    `"agent_trace"` list.

    Args:
        data (dict): Trace payload (as returned by `extract_action_trace`) with:
            - "agent_trace" (list[dict]): Each step may contain:
                * "timestamp" (str)
                * "agent" (str)
                * "message_to_agent" (str)
                * "tool_calls" (list[dict]) with keys like "tool_name", "output", ...

    Returns:
        dict: A new dict with all top-level keys from `data`, except that
        `"agent_trace"` contains only the filtered/transformed steps as described.

    Raises:
        None.
    """
        kept = []
        for step in data.get("agent_trace", []):
            keep = False
            if include_agents and (step.get("agent") in include_agents):
                keep = True
            if include_tools:
                used = {c.get("tool_name") for c in step.get("tool_calls", [])}
                if used & include_tools:
                    keep = True
            if not include_agents and not include_tools:
                keep = True  # no filters -> keep everything

            if keep:
                filtered_calls = []
                for c in step.get("tool_calls", []):
                    if not include_tools or c.get("tool_name") in include_tools:
                        oc = dict(c)
                        if isinstance(oc.get("output"), str) and len(oc["output"]) > trim_output:
                            oc["output"] = oc["output"][:trim_output] + " …[truncated]"
                        filtered_calls.append(oc)
                new_step = dict(step)
                new_step["tool_calls"] = filtered_calls if include_tools else step.get("tool_calls", [])
                if drop_empty and include_tools and not new_step["tool_calls"] and not (include_agents and step.get("agent") in include_agents):
                    continue
                kept.append(new_step)
        d2 = {k: v for k, v in data.items() if k != "agent_trace"}
        d2["agent_trace"] = kept
        return d2

    filtered = _post_filter(raw)

    # JSON encode
    s = json.dumps(filtered, ensure_ascii=False, indent=(2 if pretty else None), default=str)

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(s)
    return s

# ---- usage for “computational chemistry only” ----
json_text = extract_action_trace_json(
    "Sammy20", #<-- *implement the session name here*
    include_agents={
      "computational_chemist"
    },
    filepath="Sammy20_trace.compchem.json"
)
