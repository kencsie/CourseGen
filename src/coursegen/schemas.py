from langgraph.graph import MessagesState
from typing import List
from typing_extensions import Annotated
from operator import add
from dataclasses import dataclass
from pydantic import BaseModel, Field
from enum import Enum


from typing import TypedDict


class State(TypedDict):
    question: str  # 使用者的問題
    user_preferences: str  # 使用者學習偏好
    roadmap: dict  # 生成的roadmap
    roadmap_feedback: str  # 評論者的roadmap回饋
    roadmap_is_valid: bool  # roadmap是否通過驗證


@dataclass
class ContextSchema:
    model_name: str
    base_url: str
    openrouter_api_key: str


class DifficultyLevel(str, Enum):
    BEGINNER = "Beginner (新手 - 從零開始)"
    INTERMEDIATE = "Intermediate (有經驗 - 尋求進階)"
    ADVANCED = "Advanced (專家 - 查漏補缺)"


class LearningGoal(str, Enum):
    QUICK_START = "Quick Start (快速入門/速成)"
    DEEP_DIVE = "Deep Dive (深入精通/底層原理)"
    SKILL_APPLICATION = "Skill Application (技能應用/實戰演練)"
    TARGETED_REVIEW = "Targeted Review (目標複習/弱點加強)"


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
    is_valid: bool = Field(description="路線圖是否通過審核")
    feedback: str = Field(description="路線圖審核意見")
