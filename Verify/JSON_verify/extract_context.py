from ElAgenteQ.tool_map import tool_map
from ElAgente.config import nosql_service
import os 
import inspect
import json
import datetime
from datetime import datetime


PROJECT = os.getenv("PROJECT")

def extract_action_trace(session_name: str) -> dict:
    """
    Builds a structured, chronological trace of an agent session.

    Args:
        session_name (str): The session suffix used to select records. Messages
            with a `thread_id` matching `_{session_name}` are included.

    Returns:
        dict: A JSON-serializable export payload with:
            - session_name (str): Echo of the input session.
            - project (str): Active project identifier.
            - timestamp (str): Export creation time in "YYYY-MM-DD HH:MM:SS".
            - agent_trace (list[dict]): Ordered steps, each containing:
                * timestamp (str): Step time in "YYYY-MM-DD HH:MM:SS".
                * agent (str): Agent name for the step.
                * message_to_agent (str): The action/message sent to the agent.
                * tool_calls (list[dict]): Zero or more tool-call entries with:
                    · tool_name (str)
                    · toolcall_timestamp (str)
                    · docstring (str | None)
                    · inputs (Any)
                    · output (Any)

    Raises:
        KeyError: If expected fields (e.g., `timestamp`, `agent`,
            `formatted_history`) are missing in a message document.
        Exception: If database access fails or other unexpected errors occur.
    """
    agent_messages = nosql_service[PROJECT]['agent_history'].find(
        {"thread_id": {"$regex": f"_{session_name}"}, })
    agent_messages = list(agent_messages)
    tools = tool_map
    export_data = {
        "session_name": session_name,
        "project": PROJECT,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent_trace": []
    }

    for msg in agent_messages:
        step = {
            "timestamp": msg["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "agent": msg["agent"],
            "message_to_agent": msg["formatted_history"].get("action", ""),
            "tool_calls": []
        }

        # If tools were used
        if "tool_used" in msg["formatted_history"]:
            for tool, result in zip(msg["formatted_history"]["tool_used"],
                                    msg["formatted_history"]["tool_result"]):
                tool_name = tool["tool_name"]
                tool_args = tool["args"]
                tool_result = result

                # Get docstring if available
                docstring = None
                if tool_name in tools and hasattr(tools[tool_name].func, "__doc__"):
                    docstring = inspect.getdoc(tools[tool_name].func)

                tool_call = {
                    "tool_name": tool_name,
                    "toolcall_timestamp": tool.get("toolcall_timestamp", ""),
                    "docstring": docstring,
                    "inputs": tool_args,
                    "output": tool_result
                }

                step["tool_calls"].append(tool_call)

        export_data["agent_trace"].append(step)
    return export_data
