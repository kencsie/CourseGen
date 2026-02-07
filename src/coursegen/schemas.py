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
    roadmap_feedback: list[dict] # 評論者的roadmap回饋
    roadmap_is_valid: bool  # roadmap是否通過驗證
    validation_metadata: dict # 驗證元數據（比如贊同與反對的數量）
    iteration_count: int # 迭代次數
    termination_reason: str # 結束原因

    # ============================================================
    # TODO (Feature 3): 加入知識搜尋結果的欄位
    # 提示：儲存從 Tavily 搜尋回來的外部知識
    # ============================================================
    # knowledge_context: ???  # 提示: Optional[dict] 類型


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str
    critic_1_model: str = "anthropic/claude-3.5-sonnet"
    critic_2_model: str = "openai/gpt-4o"
    critic_3_model: str = "google/gemini-2.5-flash-thinking-exp"
    max_iterations: int = 3
    # ============================================================
    # TODO (Feature 3): 加入 Tavily API key（選用）
    # 提示：如果沒有提供，knowledge search 會被跳過
    # ============================================================
    # tavily_api_key: Optional[str] = ???

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


# ============================================================
# Feature 2: Structured Feedback Mechanism (結構化反饋機制)
# ============================================================

class IssueType(str, Enum):
    """
    問題分類 enum - 讓 critics 能明確指出問題類型

    TODO: 思考以下問題：
    1. 為什麼需要分類？跟純文字 feedback 相比有什麼好處？
    2. 這 10 個分類涵蓋了哪些面向？(結構 / 內容 / 語言...)
    """
    DAG_VIOLATION = "dag_violation"  # DAG 結構錯誤（循環依賴）
    GRANULARITY = "granularity"  # 節點數量不符合 5-15 個
    MISSING_NODE_TYPE = "missing_node_type"  # 缺少必要節點類型（先備/概念/踩雷/比較/練習）
    DIFFICULTY_MISMATCH = "difficulty_mismatch"  # 難度不符合使用者程度
    GOAL_MISMATCH = "goal_mismatch"  # 不符合學習目標（Quick Start / Deep Dive）
    LANGUAGE_ERROR = "language_error"  # 語言錯誤
    HALLUCINATION = "hallucination"  # 編造不存在的函式庫或術語
    DESCRIPTION_QUALITY = "description_quality"  # 描述不清楚
    DEPENDENCY_LOGIC = "dependency_logic"  # 依賴關係不合理
    OTHER = "other"  # 其他問題


class SeverityLevel(str, Enum):
    """
    嚴重程度分級

    TODO: 思考這三個等級如何影響 generator 的修正優先順序？
    """
    CRITICAL = "critical"  # 嚴重問題，必須修正（例如：DAG violation）
    MAJOR = "major"      # 重要問題，應該修正（例如：缺少節點類型）
    MINOR = "minor"      # 次要問題，建議修正（例如：描述可以更清楚）


class StructuredIssue(BaseModel):
    """
    單一結構化問題

    TODO: 比較這個 model 和原本的純文字 feedback，想想看：
    - 哪些資訊變得更明確了？
    - generator 如何利用 suggested_fix 來改進？
    """
    issue_type: IssueType = Field(description="問題類型")
    severity: SeverityLevel = Field(description="嚴重程度")
    description: str = Field(description="問題描述")
    affected_nodes: List[str] = Field(
        default_factory=list,
        description="受影響的節點 ID（如果適用）"
    )
    suggested_fix: str = Field(description="建議的修正方向")


class StructuredValidationResult(BaseModel):
    """
    結構化的驗證結果（取代原本的 RoadmapValidationResult）

    TODO: 這個新 model 如何讓 aggregator 更容易整合三個 critics 的意見？
    """
    critic_name: str = Field(description="Critic名稱")
    model_name: str = Field(description="LLM模型名稱")
    is_valid: bool = Field(description="整體驗證結果")
    issues: List[StructuredIssue] = Field(
        default_factory=list,
        description="發現的所有問題"
    )
    summary: str = Field(description="整體評價總結")


class AggregatedFeedback(BaseModel):
    """
    整合三個 critics 的反饋

    TODO: 思考 aggregator_node 如何使用這個 model：
    - 如何偵測「共識問題」（2+ critics 都提到）？
    - 為什麼要區分 consensus_issues 和 individual_issues？
    """
    consensus_issues: List[StructuredIssue] = Field(
        default_factory=list,
        description="多數 critics (2+) 都指出的問題"
    )
    individual_issues: List[StructuredIssue] = Field(
        default_factory=list,
        description="單一 critic 提出的問題"
    )
    overall_summary: str = Field(description="整合後的總結")


# ============================================================
# Feature 3: Knowledge Search Integration (知識搜尋整合)
# ============================================================

class SearchResult(BaseModel):
    """
    Tavily 搜尋結果

    TODO: 這個 model 如何幫助 LLM 驗證資訊的真實性？
    """
    title: str = Field(description="搜尋結果標題")
    url: str = Field(description="來源 URL")
    content: str = Field(description="內容摘要")
    score: float = Field(description="相關性評分 (0-1)")


class KnowledgeContext(BaseModel):
    """
    外部知識上下文

    TODO: 思考這個 context 在 workflow 中的流動：
    knowledge_search_node → roadmap_node (作為 prompt 的一部分)
    """
    query: str = Field(description="搜尋查詢")
    results: List[SearchResult] = Field(description="搜尋結果")
    synthesized_knowledge: str = Field(
        description="LLM 整合後的知識摘要"
    )