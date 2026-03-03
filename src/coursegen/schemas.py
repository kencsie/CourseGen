from typing import List, Literal, Optional, Annotated
from dataclasses import dataclass
from pydantic import BaseModel, Field
from enum import Enum
from typing import TypedDict


def dict_merge_reducer(current: dict, new: dict) -> dict:
    """
    自定義 reducer 用於 dict 字段：
    將 new 的 key-value 合併到 current 中（淺合併）。
    """
    merged = current.copy()
    merged.update(new)
    return merged


class AppState(TypedDict):
    """Top-level graph state — 僅負責兩個 subgraph 之間的交接。"""
    question: str
    user_preferences: str
    topic_keyword: str                                 # LLM 從問句提取的精簡主題關鍵字
    roadmap: dict                                      # RoadmapSubgraph 輸出，ContentSubgraph 輸入
    content_order: list[str]                           # ContentSubgraph 輸出
    content_map: Annotated[dict, dict_merge_reducer]   # ContentSubgraph 輸出
    content_failed_nodes: list[str]                    # ContentSubgraph 輸出


class RoadmapState(TypedDict):
    """Roadmap subgraph 私有 state。"""
    # 從 AppState 橋接進來
    question: str
    user_preferences: str
    topic_keyword: str                                 # 輸出回 AppState
    roadmap: dict                                      # 輸出回 AppState
    # 私有欄位
    roadmap_feedback: list[dict]
    roadmap_is_valid: bool
    roadmap_latest_feedback: str
    roadmap_retry_target: str
    validation_metadata: dict
    iteration_count: int
    termination_reason: str
    knowledge_context: dict
    roadmap_search_queries_history: list[list[str]]
    roadmap_search_urls_seen: list[str]


class ContentState(TypedDict):
    """Content subgraph 私有 state。"""
    # 從 AppState 橋接進來
    roadmap: dict
    user_preferences: str
    topic_keyword: str                                 # 從 AppState 橋接進來
    content_order: list[str]                           # 輸出回 AppState
    content_map: Annotated[dict, dict_merge_reducer]   # 輸出回 AppState
    content_failed_nodes: list[str]                    # 輸出回 AppState
    # 私有欄位
    content_current_index: int
    content_node_knowledge: dict
    content_node_feedback: str
    content_node_retries: int
    content_node_retry_target: str
    content_node_feedback_history: list[str]
    content_search_queries_history: list[list[str]]
    content_search_urls_seen: list[str]


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str
    tavily_api_key: Optional[str] = None
    roadmap_critic_model: str = "google/gemini-3-flash-preview"
    max_iterations: int = 5
    content_model: str = "google/gemini-3-flash-preview"
    content_critic_model: str = "google/gemini-3-flash-preview"
    content_max_retries: int = 5
    cheap_model: str = "google/gemini-3-flash-preview"


class Language(str, Enum):
    ZH_TW = "Traditional Chinese (繁體中文)"
    EN = "English (英文)"


class UserPreferences(BaseModel):
    language: Language = Field(
        default=Language.ZH_TW,
        description="生成roadmap與內容的語言",
    )

    def to_prompt_context(self) -> str:
        return f"- Preferred Language: {self.language.value}"


class NodeType(str, Enum):
    PREREQUISITE = "prerequisite"
    CONCEPT = "concept"
    PITFALL = "pitfall"
    COMPARISON = "comparison"
    PRACTICE = "practice"


class RoadmapNode(BaseModel):
    id: str = Field(..., description="節點的獨特ID, 比如:'1', 'setup'")
    label: str = Field(..., description="節點的名稱")
    description: str = Field(..., description="2-3 句話描述此節點涵蓋的內容與學習重點")
    type: NodeType = Field(
        ...,
        description="節點類型：prerequisite（先備知識診斷與補齊）、concept（核心概念講解）、pitfall（踩雷與常見錯誤）、comparison（概念比較）、practice（統整練習）",
    )
    dependencies: List[str] = Field(default_factory=list, description="父節點ID串列")


class Roadmap(BaseModel):
    topic: str = Field(..., description="roadmap的主題")
    nodes: List[RoadmapNode]


class RoadmapValidationResult(BaseModel):
    feedback: str = Field(description="詳細回饋")
    is_valid: bool = Field(description="驗證結果")
    retry_target: Literal["search", "generation"] = Field(
        description="若 is_valid=False，決定 retry 回到 search 還是 generation"
    )


class SearchResult(BaseModel):
    """
    Tavily 搜尋結果
    """

    title: str = Field(description="搜尋結果標題")
    url: str = Field(description="來源 URL")
    content: str = Field(description="內容摘要")
    score: float = Field(description="相關性評分 (0-1)")
    raw_content: Optional[str] = Field(default=None, description="完整內容")


class SourceRef(BaseModel):
    """內容引用來源"""
    title: str = Field(description="網頁標題")
    url: str = Field(description="來源 URL")
    snippet: str = Field(description="Tavily 擷取的相關片段")


class KnowledgeContext(BaseModel):
    """
    外部知識上下文

    TODO: 思考這個 context 在 workflow 中的流動：
    knowledge_search_node → roadmap_node (作為 prompt 的一部分)
    """

    query: str = Field(description="搜尋查詢")
    results: List[SearchResult] = Field(description="搜尋結果")
    synthesized_knowledge: str = Field(description="LLM 整合後的知識摘要")


# ============================================================
# Content Models — 五種節點類型的教學內容結構
# ============================================================


_REASONING_DESC = (
    "生成前的思考過程：(1) 列出可用的來源編號及其重點內容 "
    "(2) 規劃內容結構與引用對應"
)


class PrerequisiteContent(BaseModel):
    """先備知識節點的教學內容：診斷學習者是否具備前置知識，並提供補救方向。"""

    reasoning: str = Field(description=_REASONING_DESC)
    overview: str = Field(
        description="用 2-3 句話概述這個先備知識為何重要、以及它與後續學習的關聯。語氣親切但專業。"
    )
    checklist: List[str] = Field(
        description="1-3 個具體的自我檢核問題，讓學習者判斷自己是否已具備此先備知識。每個問題應可用『是/否』回答，例如：'你能解釋什麼是變數嗎？'"
    )
    remediation: List[str] = Field(
        description="針對每個檢核點未通過的學習者，提供具體的補救方向或推薦資源（2-4 項）。例如：'建議先閱讀 Python 官方教程的第 3 章：資料型態'"
    )


class ConceptContent(BaseModel):
    """核心概念節點的教學內容：深入講解一個概念或技能，建立正確的心智模型。"""

    reasoning: str = Field(description=_REASONING_DESC)
    explanation: str = Field(
        description="概念的完整講解（300-600 字）。必須包含：定義、為什麼重要、核心運作原理。使用類比或比喻幫助理解。避免只列點，要有段落式的解說。"
    )
    key_points: List[str] = Field(
        description="3-5 個關鍵要點，每個要點用一句話精煉表達。這些是學習者讀完後必須記住的核心觀念。"
    )
    examples: List[str] = Field(
        description="1-3 個具體的範例或程式碼片段，展示此概念的實際應用。每個範例需有簡短說明。"
    )


class PitfallContent(BaseModel):
    """踩雷節點的教學內容：警告常見錯誤與陷阱，幫助學習者避開彎路。"""

    reasoning: str = Field(description=_REASONING_DESC)
    pitfalls: List[str] = Field(
        description="3-5 個最常見的錯誤或陷阱。每個條目包含：(1) 錯誤描述、(2) 為什麼會犯這個錯、(3) 正確做法。格式範例：'❌ 錯誤：直接修改 state → 原因：React 使用淺比較偵測變化 → ✅ 正確：使用 setState 或展開運算子'"
    )
    warning_signs: List[str] = Field(
        description="2-3 個警示信號，幫助學習者在實作時早期發現自己踩到雷。例如：'如果你發現 UI 沒有更新，很可能是直接修改了 state'"
    )


class ComparisonContent(BaseModel):
    """比較節點的教學內容：釐清容易混淆的概念或工具差異。"""

    reasoning: str = Field(description=_REASONING_DESC)
    subject_a: str = Field(description="比較對象 A 的名稱")
    subject_b: str = Field(description="比較對象 B 的名稱")
    comparison_table: List[dict] = Field(
        description="3-6 個比較維度，每個維度是一個 dict，格式為 {'dimension': '比較面向', 'a': 'A 的表現', 'b': 'B 的表現'}。涵蓋：用途、效能、學習曲線、適用場景等。"
    )
    when_to_use: str = Field(
        description="總結性建議（2-3 句話）：什麼情境用 A、什麼情境用 B、有沒有可以混用的情況。"
    )


class PracticeContent(BaseModel):
    """練習節點的教學內容：用實作任務整合前面所學，強化記憶與應用能力。"""

    reasoning: str = Field(description=_REASONING_DESC)
    objective: str = Field(
        description="練習目標（1-2 句話）：完成這個練習後，學習者應該能做到什麼。"
    )
    tasks: List[str] = Field(
        description="2-4 個由簡到難的子任務，組成一個完整的練習。每個任務描述清楚輸入、操作、預期產出。"
    )
    expected_output: str = Field(
        description="完成練習後的可觀察成果描述。例如：'一個能在終端顯示天氣資訊的 Python 腳本'"
    )
    hints: List[str] = Field(
        description="1-3 個提示，在學習者卡住時提供方向，但不直接給出答案。"
    )


class SearchQueryResult(BaseModel):
    """Search query generation 的結構化輸出"""
    reasoning: str = Field(
        description="思考過程：分析節點主題、考慮 critic feedback（如有），決定最佳搜尋方向"
    )
    queries: list[str] = Field(
        description="3 short keyword queries: first is topic_keyword + node label, others are topic_keyword + 1-2 word keyword"
    )


class RoadmapSearchQueryResult(BaseModel):
    """Roadmap search query generation 的結構化輸出"""
    topic_keyword: str = Field(
        description="從使用者問句提取的精簡主題關鍵字，例：'Minecraft 1.21.11'、'桌球殺球'"
    )
    reasoning: str = Field(
        description="思考過程：分析使用者問題與 critic feedback（如有），決定最佳搜尋方向"
    )
    queries: list[str] = Field(
        description="3 short keyword queries: first is topic_keyword only, others are topic_keyword + 1-2 word keyword"
    )


class SourceScore(BaseModel):
    index: int = Field(description="來源編號（從 1 開始）")
    reason: str = Field(description="評分原因")
    score: int = Field(description="相關性評分 0-10")


class SourceFilterResponse(BaseModel):
    results: list[SourceScore]


class SectionRemovalResponse(BaseModel):
    reason: str = Field(
        description="Brief reasoning for which sections to remove and why."
    )
    remove_indices: list[int] = Field(
        description="1-based paragraph numbers to REMOVE. Empty list = keep all."
    )


class SourceSelectionResponse(BaseModel):
    reason: str = Field(
        description="Brief reasoning for source selection."
    )
    keep_indices: list[int] = Field(
        description="1-based source numbers to KEEP, ordered by importance."
    )


class ContentValidationResult(BaseModel):
    """Content critic 的審核結果"""

    feedback: str = Field(
        description="具體的審核意見。先逐一分析五個維度，再得出結論。不通過時必須指出哪些部分不合格、如何改進"
    )
    is_valid: bool = Field(
        description="內容是否通過審核：true 表示品質合格，false 表示需要重新生成。必須與上方 feedback 的分析結論一致"
    )
    retry_target: Literal["search", "generation"] = Field(
        description="若 is_valid=False，決定 retry 回到 search 還是 generation"
    )
