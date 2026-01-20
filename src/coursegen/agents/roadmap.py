from langchain.chat_models import init_chat_model
from coursegen.prompts.answer import ANSWER_PROMPT
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime


def roadmap_node(state: State, runtime: Runtime[ContextSchema]):
    model = init_chat_model(
        runtime.context.model_name,
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
    )
    response = model.invoke(
        ANSWER_PROMPT.format(
            question=state["messages"][-1].content, retrieved_doc=state["retrieved_doc"]
        )
    )
    return {"messages": [response]}
