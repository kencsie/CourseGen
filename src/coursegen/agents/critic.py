from coursegen.schemas import RoadmapValidationResult
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import ROADMAP_CRITIC_PROMPT
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime

def critic_1_node(state: State, runtime: Runtime[ContextSchema]) -> dict:                                                    
    model = init_chat_model(
        model=runtime.context.critic_1_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_1"
    response.model_name = runtime.context.critic_1_model

    return {
        "critics": [response.model_dump()]
    }                                                                                                           

def critic_2_node(state: State, runtime: Runtime[ContextSchema]) -> dict:                                                    
    model = init_chat_model(
        model=runtime.context.critic_2_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_2"
    response.model_name = runtime.context.critic_2_model

    return {
        "critics": [response.model_dump()]
    }   

def critic_3_node(state: State, runtime: Runtime[ContextSchema]) -> dict:                                                    
    model = init_chat_model(
        model=runtime.context.critic_3_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_3"
    response.model_name = runtime.context.critic_3_model

    return {
        "critics": [response.model_dump()]
    }   

def aggregator_node(state: State) -> dict:                                                                                   
    """根據多數決，得出此roadmap是否正確"""                                                                                 
                                                                                                                                                                                       
    critics = [RoadmapValidationResult(**c) for c in state["critics"]]                                                                                                                                                                                                                                                                                 
    valid_votes = sum(1 for c in critics if c.is_valid)                                                                      
    is_valid = valid_votes >= 2  # 至少要2/3，才算通過                                                                               
    feedback = [c.model_dump() for c in critics]                                                                                                                                                                                                                                                                                       
                                                        
    metadata = {                                                                                                             
        "valid_votes": valid_votes,                                                                                          
        "total_critics": 3,                                                                                                  
        "consensus_level": "unanimous" if valid_votes in [0, 3] else "majority"                                              
    }                                                                                                                        
                                                                                                                                                                                                                                    
    return {                                                                                                                 
        "roadmap_is_valid": is_valid,                                                                                        
        "roadmap_feedback": feedback,                                                                                        
        "validation_metadata": metadata                                                                                      
    }

def roadmap_critic_node(state: State, runtime: Runtime[ContextSchema]):
    model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    return {
        "roadmap_feedback": response.feedback,
        "roadmap_is_valid": response.is_valid,
    }
