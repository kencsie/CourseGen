# CourseGen — CLAUDE.md

LangGraph + Pydantic + Streamlit 多代理系統。Python 3.12，UI 與 workflow 同進程。

## 程式碼地圖

| 想找什麼 | 去哪查 |
|---|---|
| LangGraph workflow | `src/coursegen/workflows/` |
| State / ContextSchema / 所有 Pydantic schema | `src/coursegen/schemas.py` |
| Agent 與 critic | `src/coursegen/agents/` |
| Prompt 模板 | `src/coursegen/prompts/` |
| Tavily / 內容清洗 | `src/coursegen/utils/` |
| Streamlit UI | `src/coursegen/ui/` |
| 認證 / DB / CRUD | `src/coursegen/db/` |
| 評估 CLI | `src/coursegen/eval/` |

## 開發要點
### 工具鏈
- 套件管理 `uv`，lint/format `ruff`，code review `.claude/skills/code-review/`

### 工作流程（Steering Loop）
收到需求後，照下列順序執行；任一階段失敗，回到第 1 步修正後重跑該階段：

1. **寫程式碼** — 依需求動筆，遵守「修改細節」規範
2. **`uv run ruff check src/`** — 不通過則修，重跑
3. **`uv run pytest`** — 若有對應測試則跑，不通過則修，重跑
4. **`/code-review` skill** — 違反 CLAUDE.md 規範則修，重跑

第 2、3 步由 Stop hook 自動執行（見 `.claude/hooks/steering-loop.sh`），失敗會自動 block 並把錯誤回饋給 AI。第 4 步由使用者手動觸發。

**重試上限**：同一階段連續修 3 次仍失敗，停下向使用者回報，不繼續重試。

## 修改細節
### 寫 LLM workflow / schema 時
- Content / search query schema 第一欄位必須是 `reasoning: str`
- TypedDict 累積型 dict state 欄位必須標 `Annotated[dict, dict_merge_reducer]`
- 模型名 / API key / retry 上限一律從 `ContextSchema` 取，禁止 `os.getenv()` 或 hardcode

### 改 `db/crud.py` 時
- 新增函式必須 `(*, user_id: str | None)` 簽名，不得設預設值
- 寫入函式入口必須對 `user_id == 'example'` raise `PermissionError`

### 新增節點類型時
必須同時改 5 處：`schemas.py` / `prompts/content.py` / `agents/content.py:CONTENT_MODELS` / `agents/content.py:CONTENT_PROMPTS` / `ui/components/content_renderer.py`

### 改評估時
- L1 / L2 metric 禁止呼叫 LLM API
- L3 judge 必須跨廠商（OpenAI / Anthropic / Google）
