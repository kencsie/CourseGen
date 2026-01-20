from langgraph.graph import MessagesState
from typing_extensions import Annotated
from operator import add
from dataclasses import dataclass


class State(MessagesState):
    retrieved_doc: Annotated[list[dict], add]


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str
