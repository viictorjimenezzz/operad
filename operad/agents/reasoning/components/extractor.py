"""Text-to-schema extractor leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Extractor(Agent[In, Out]):
    """Turn unstructured input into a typed Pydantic schema.

    The canonical NLP "structured extraction" task. The output class's
    ``Field(description=...)`` annotations drive how each slot is
    populated — they're rendered verbatim into the system prompt via
    ``<output_schema>``.

    A canonical few-shot::

        from pydantic import BaseModel, Field
        from operad import Example

        class Sentence(BaseModel):
            text: str = Field(description="A free-form sentence.")

        class Person(BaseModel):
            name: str = Field(default="", description="The person's name.")
            age: int = Field(default=0, description="Age in years.")

        examples = (
            Example[Sentence, Person](
                input=Sentence(text="Ada Lovelace was 36 when she died."),
                output=Person(name="Ada Lovelace", age=36),
            ),
        )
    """

    role = (
        "You are a precise information extractor. You populate structured "
        "schemas from unstructured input without inventing facts."
    )
    task = (
        "Read the input carefully and fill in every field of the output "
        "schema. If a field's value is not present in the input, use the "
        "field's natural empty value (empty string, empty list, null)."
    )
    rules = (
        "Never invent information not supported by the input.",
        "Match the output schema's field types and descriptions exactly.",
    )
    default_sampling = {"temperature": 0.0}
