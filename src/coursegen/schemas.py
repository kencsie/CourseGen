from typing import List, Optional, Annotated
from dataclasses import dataclass
from pydantic import BaseModel, Field
from enum import Enum
from typing import TypedDict


def critics_reducer(current: list[dict], new: list[dict]) -> list[dict]:
    """
    自定義 reducer 用於 critics 字段：
    - 如果 new 是空列表 []，則清空 current（返回空列表）
    - 否則將 new 追加到 current（add 行為）
    """
    if new == []:  # 空列表作為清空信號
        return []
    return current + new


class State(TypedDict):
    question: str  # 使用者的問題
    user_preferences: str  # 使用者學習偏好
    roadmap: dict  # 生成的roadmap
    critics: Annotated[list[dict], critics_reducer]
    roadmap_feedback: list[dict]  # 評論者的roadmap回饋
    roadmap_is_valid: bool  # roadmap是否通過驗證
    validation_metadata: dict  # 驗證元數據（比如贊同與反對的數量）
    iteration_count: int  # 迭代次數
    termination_reason: str  # 結束原因
    knowledge_context: dict  # Tavily 知識搜尋結果


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str
    tavily_api_key: Optional[str] = None
    critic_1_model: str = "anthropic/claude-3.5-sonnet"
    critic_2_model: str = "openai/gpt-4o"
    critic_3_model: str = "google/gemini-2.5-flash-thinking-exp"
    max_iterations: int = 3


class DifficultyLevel(str, Enum):
    BEGINNER = "Beginner (新手 - 從零開始)"
    INTERMEDIATE = "Intermediate (有經驗 - 尋求進階)"
    ADVANCED = "Advanced (專家 - 查漏補缺)"


class LearningGoal(str, Enum):
    QUICK_START = "Quick Start (快速入門/速成)"
    DEEP_DIVE = "Deep Dive (深入精通/底層原理)"


class Language(str, Enum):
    ZH_TW = "Traditional Chinese (繁體中文)"
    EN = "English (英文)"


class UserPreferences(BaseModel):
    level: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="當前使用者知識水平",
    )
    goal: LearningGoal = Field(
        default=LearningGoal.DEEP_DIVE, description="主要學習目標"
    )
    language: Language = Field(
        default=Language.ZH_TW,
        description="生成roadmap與內容的語言",
    )

    # 這是給 Prompt 用的 helper method，轉成自然的英文描述
    def to_prompt_context(self) -> str:
        return f"""
        - Target Audience Level: {self.level.name}
        - Learning Goal: {self.goal.name}
        - Preferred Language: {self.language.value}
        """


class RoadmapNode(BaseModel):
    id: str = Field(..., description="節點的獨特ID, 比如:'1', 'setup'")
    label: str = Field(..., description="節點的名稱")
    description: str = Field(..., description="一句話的總結")
    dependencies: List[str] = Field(default_factory=list, description="父節點ID串列")


class Roadmap(BaseModel):
    topic: str = Field(..., description="roadmap的主題")
    nodes: List[RoadmapNode]


class RoadmapValidationResult(BaseModel):
    critic_name: str = Field(description="Critic名稱(critic_1/critic_2/critic_3)")
    model_name: str = Field(description="LLM模型名稱")
    feedback: str = Field(description="詳細回饋")
    is_valid: bool = Field(description="驗證結果")


class SearchResult(BaseModel):
    """
    Tavily 搜尋結果
    """

    title: str = Field(description="搜尋結果標題")
    url: str = Field(description="來源 URL")
    content: str = Field(description="內容摘要")
    score: float = Field(description="相關性評分 (0-1)")
    raw_content: str = Field(description="完整內容")


class KnowledgeContext(BaseModel):
    """
    外部知識上下文

    TODO: 思考這個 context 在 workflow 中的流動：
    knowledge_search_node → roadmap_node (作為 prompt 的一部分)
    """

    query: str = Field(description="搜尋查詢")
    results: List[SearchResult] = Field(description="搜尋結果")
    synthesized_knowledge: str = Field(description="LLM 整合後的知識摘要")
