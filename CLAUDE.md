# CourseGen — CLAUDE.md

LangGraph + Pydantic + Streamlit 多代理系統。Python 3.12，UI 與 workflow 同進程。

## 文件索引

| 項目 | 位置 |
|---|---|
| docs/ 結構與更新規則 | `docs/README.md` |
| 整體架構 | README「Architecture Overview」、`src/`（見程式碼地圖） |
| 設計信念 / 決策理由 | `docs/design-docs/` |
| invariant 的契約與保證 | `tests/` |
| 進行中 / 完成的計劃 | `docs/exec-plans/` |

## 程式碼地圖

| 項目 | 位置 |
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
- 套件管理：`uv`；lint / format：`ruff`；code review：`.claude/skills/code-review/`

### 工作流程（Steering Loop）
開發依下列順序進行；任一階段失敗時，回到第 1 步修正後重新執行該階段。

1. **撰寫程式碼** — 依需求實作，符合「既有 invariant」清單
2. **`uv run ruff check src/`** — 未通過時修正並重新執行
3. **`uv run pytest`** — 有對應測試時執行，未通過時修正並重新執行
4. **`/code-review` skill** — 違反 CLAUDE.md 所列 invariant 時修正並重新執行

第 2、3 步由 Stop hook 自動執行（見 `.claude/hooks/steering-loop.sh`）；失敗時自動中斷，並將錯誤回饋給 AI。第 4 步由使用者手動觸發。

**重試上限**：同一階段連續修正 3 次仍失敗時，停止並向使用者回報，不再重試。

## 既有 invariant（尚未遷移成測試）
> 以下 invariant 尚無對應的自動化測試，目前以人工遵循；補上測試後即移交 `tests/`，並從本清單移除。

### LLM workflow / schema
- Content / search query schema 的第一個欄位是 `reasoning: str`
- TypedDict 的累積型 dict state 欄位標註 `Annotated[dict, dict_merge_reducer]`
- 模型名 / API key / retry 上限來自 `ContextSchema`，不使用 `os.getenv()` 或硬編碼

### `db/crud.py`
- 函式簽名為 `(*, user_id: str | None)`，沒有預設值
- 寫入函式對 `user_id == 'example'` 拋出 `PermissionError`

### 評估
- L1 / L2 metric 不呼叫 LLM API
- L3 judge 跨廠商（OpenAI / Anthropic / Google）
