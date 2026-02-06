from typing import List, Optional, Annotated, Literal
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
    roadmap: Optional[dict]  # 生成的roadmap
    critics: Annotated[list[dict], critics_reducer]
    roadmap_feedback: list[dict] # 評論者的roadmap回饋
    roadmap_is_valid: bool  # roadmap是否通過驗證
    validation_metadata: Optional[dict] # 驗證元數據（比如贊同與反對的數量）
    iteration_count: int  # 當前迭代次數
    max_iterations: int  # 最大允許迭代次數
    termination_reason: Optional[str]  # 終止原因（"validation_passed" 或 "max_iterations_reached"）
    knowledge_context: Optional[dict]  # 外部知識上下文
    search_performed: bool  # 是否已執行搜尋


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str
    critic_1_model: str = "anthropic/claude-3.5-sonnet"
    critic_2_model: str = "openai/gpt-4o"
    critic_3_model: str = "google/gemini-2.5-flash-thinking-exp"
    max_iterations: int = 3  # 默認最大迭代次數

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


class IssueType(str, Enum):
    """問題類型枚舉"""
    MISSING_NODE_TYPE = "missing_node_type"  # 缺少特定類型的節點
    INVALID_DEPENDENCY = "invalid_dependency"  # 無效的依賴關係
    WRONG_DIFFICULTY = "wrong_difficulty"  # 難度不符
    WRONG_GOAL = "wrong_goal"  # 學習目標不符
    WRONG_LANGUAGE = "wrong_language"  # 語言不符
    POOR_DESCRIPTION = "poor_description"  # 描述不清楚
    HALLUCINATED_CONTENT = "hallucinated_content"  # 編造內容
    GRANULARITY_ISSUE = "granularity_issue"  # 顆粒度問題
    LINEAR_STRUCTURE = "linear_structure"  # 過於線性的結構
    CIRCULAR_DEPENDENCY = "circular_dependency"  # 循環依賴


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


class StructuredIssue(BaseModel):
    """結構化問題描述"""
    issue_type: IssueType = Field(description="問題類型")
    severity: Literal["critical", "major", "minor"] = Field(description="嚴重程度")
    location: str = Field(description="問題位置，如 'node: basics-1' 或 'overall structure'")
    description: str = Field(description="問題描述")
    suggested_fix: str = Field(description="具體的修正建議")


class RoadmapValidationResult(BaseModel):
    critic_name: str = Field(description="Critic名稱(critic_1/critic_2/critic_3)")
    model_name: str = Field(description="LLM模型名稱")
    is_valid: bool = Field(description="驗證結果")
    issues: List[StructuredIssue] = Field(default_factory=list, description="結構化問題列表")
    feedback: str = Field(description="詳細回饋（向後兼容）")
    strengths: List[str] = Field(default_factory=list, description="優點列表")


class AggregatedFeedback(BaseModel):
    """整合後的回饋"""
    is_valid: bool = Field(description="整體驗證結果")
    critical_issues: List[StructuredIssue] = Field(default_factory=list, description="所有嚴重問題")
    consensus_issues: List[StructuredIssue] = Field(default_factory=list, description="2+個critics同意的問題")
    summary: str = Field(description="給generator的高層總結")


class SearchResult(BaseModel):
    """搜尋結果"""
    title: str = Field(description="標題")
    url: str = Field(description="URL")
    content: str = Field(description="內容摘要")
    score: float = Field(description="相關性分數")


class KnowledgeContext(BaseModel):
    """外部知識上下文"""
    query: str = Field(description="搜尋查詢")
    results: List[SearchResult] = Field(description="搜尋結果列表")
    summary: str = Field(description="LLM 生成的關鍵發現總結")