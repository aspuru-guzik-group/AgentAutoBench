from ElAgente.Agent import StructureOutputAgent
from pydantic import BaseModel, Field
from typing import Annotated
from pathlib import Path
import csv, json

# ---- Schema ----
class Result(BaseModel):
    """
    Schema of structured facts extracted from a scientific passage.

    This model captures (1) whether a text reports a pKa value for
    chlorofluoroacetic acid and (2) whether it explicitly mentions a linear
    regression model.

    Attributes:
        pKa_of_chlorofluoroacetic_acid (float | str):
            The reported pKa of chlorofluoroacetic acid. Use a numeric value
            when the text provides one; otherwise set the string
            "Do Not Exist" to indicate the value is not reported.
        has_linear_regression_model (bool):
            True if the text explicitly indicates the presence of a linear
            regression (e.g., mentions "linear regression", provides an
            equation such as y = ax + b, or reports R²/R^2); False otherwise.

    Raises:
        pydantic.ValidationError:
            Raised by Pydantic if data supplied to construct this model does not
            conform to the declared field types.
    """
    
    pKa_of_chlorofluoroacetic_acid: float | str = Field(
        ..., description="the pka value of the chlorofluoroacetic_acid, Do Not Exist if not reported"
    )
    has_linear_regression_model: bool = Field(
        ..., description="True if the text explicitly reports a linear regression model (mentions 'linear regression', an equation, or R²)."
    )

# ---- Your original function (unchanged) ----
def test_expert(message2agent: Annotated[str, Field(description="Message to the agent")]):
    """
    Parses a message with a structured-output agent and returns schema-validated fields.

    The function instantiates a `StructureOutputAgent` configured with the
    `Result` schema, sends brief system guidance, streams the graph state for the
    provided message, clears the agent's memory, and returns the structured
    extraction from the `"structure_output"` field.

    Args:
        message2agent (str): The content to be parsed for:
            - `pKa_of_chlorofluoroacetic_acid`
            - `has_linear_regression_model`

    Returns:
        Result: Structured data validated against the `Result` Pydantic schema.
        (Depending on the agent implementation, this may be a Pydantic model
        instance or a JSON-serializable dict with the same fields.)

    Raises:
        pydantic.ValidationError: If the agent's output does not conform to `Result`.
        KeyError: If `"structure_output"` is missing from the returned graph state.
        Exception: Any lower-level errors from the model call/streaming layer.
    """
    agent = StructureOutputAgent(model="gpt-4o", agent_schema=Result)
    agent.append_system_message("You are a parsing agent.")
    agent.append_system_message("")
    result = agent.stream_return_graph_state(message2agent)
    agent.clear_memory()
    return result["structure_output"]

# ---- Read .md, run parser, and export to CSV ----
src_path = "/h/400/skaxu/ElAgente/pKa_test_3/pKa_calculation_report.md"  # <-- update to your .md path
text = Path(src_path).read_text(encoding="utf-8", errors="ignore")

payload = test_expert("This is the final answer you need to extract result from:\n" + text)

row = {
    "file": src_path,
    "pKa_of_chlorofluoroacetic_acid": payload.get("pKa_of_chlorofluoroacetic_acid"),
    "has_linear_regression_model": payload.get("has_linear_regression_model"),
}

csv_path = "extracted_results_from_md.csv"
file_exists = Path(csv_path).exists()

with open(csv_path, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=row.keys())
    if not file_exists:
        writer.writeheader()
    writer.writerow(row)

print(f"Wrote 1 row to {csv_path}")

