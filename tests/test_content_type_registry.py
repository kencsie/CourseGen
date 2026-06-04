"""守住 CLAUDE.md invariant #6：新增節點類型必須在 5 個登記表同步。

以 NodeType 為真相來源，比對三個查詢表（CONTENT_MODELS / CONTENT_PROMPTS /
_RENDERERS）的鍵。任一表漏掉某型別 → 對應那條測試變紅，並指出是哪個表。
（schemas.py 的 model class 由 CONTENT_MODELS 的值間接覆蓋。）
"""
from coursegen.agents.content import CONTENT_MODELS
from coursegen.prompts.content import CONTENT_PROMPTS
from coursegen.schemas import NodeType
from coursegen.ui.components.content_renderer import _RENDERERS

EXPECTED = {nt.value for nt in NodeType}


def test_content_models_registered_for_all_types():
    assert set(CONTENT_MODELS) == EXPECTED


def test_content_prompts_registered_for_all_types():
    assert set(CONTENT_PROMPTS) == EXPECTED


def test_renderers_registered_for_all_types():
    assert set(_RENDERERS) == EXPECTED
