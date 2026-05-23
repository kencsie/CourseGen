---
name: code-review
description: 依 CourseGen CLAUDE.md 的 repo-unique 規範審查當前 diff。在 commit / merge 前手動觸發；不替代 ruff / ty，而是檢查 lint 抓不到的設計違規（schema reasoning 欄位、ContextSchema 注入、user_id keyword-only、節點類型五處同步等）。
---

# CourseGen 設計規範審查

## 何時使用

- 使用者要求 `/code-review` 或「幫我審 PR / diff」
- Commit 前自我檢查
- 開新 PR 前的把關

不要在每次小改動都跑 — 這是 review 等級的 sensor，跑一次要錢。

## 任務

讀取當前 git diff，逐條對照 `CLAUDE.md` 規範，找出違規處並提供修法。**不重複 ruff/ty 已涵蓋的事**（line length、import 排序、型別）— 那些自動化工具會抓。專注於設計層級的違規。

## 執行步驟

1. 跑 `git diff main...HEAD --stat` 看改動範圍；若分支與 main 一致改跑 `git diff --stat HEAD`
2. 對每個改動檔案，跑 `git diff main...HEAD -- <file>`（或 `HEAD`）讀內容
3. 逐條跑下方檢查清單，記錄違規
4. 依輸出格式回報

## 檢查清單（對齊 CLAUDE.md）

### 1. Schema 規範
- [ ] 新增給 LLM 的 content / search query schema：第一欄位是否為 `reasoning: str`？
- [ ] 新 Pydantic schema 是否放在 `schemas.py`，而非散落到 agent / workflow？
- [ ] 新增 router 用的決策欄位是否用 `Literal[...]` enum，而非寬鬆 `str`？
- [ ] TypedDict state 新增需累積的 dict 欄位，是否標 `Annotated[dict, dict_merge_reducer]`？

### 2. LLM 呼叫 / 設定來源
- [ ] 是否從 `ContextSchema` 取 API key？有沒有 `os.getenv("OPENROUTER_API_KEY")` 或 `os.getenv("TAVILY_API_KEY")`？
- [ ] 模型名 / retry 上限是否從 `ContextSchema` 取？有沒有 hardcode 字串如 `"openai/gpt-5.2"` 或數字如 `max_retries=5`？
- [ ] 是否將使用者 key 寫進 `.env.example` 或 commit 到 git？

### 3. 資料隔離（`db/crud.py` 改動）
- [ ] 新增 CRUD 函式是否用 `(*, user_id: str | None)` keyword-only 簽名？
- [ ] 簽名是否設了 `user_id = None` 預設值？（不允許）
- [ ] 寫入函式入口是否 raise `PermissionError` 對 `user_id == 'example'`？
- [ ] 在 eval CLI 以外的程式碼是否傳了 `user_id=None`？
- [ ] UI 對 demo user 是否 disable 寫入按鈕（前端第一道防線）？

### 4. 節點類型擴展
若 diff 改動涉及新增節點類型，5 處是否齊：
- [ ] `schemas.py` — 新 Pydantic content schema（第一欄位 `reasoning`）
- [ ] `prompts/content.py` — 新 prompt 模板
- [ ] `agents/content.py:CONTENT_MODELS` — 新類型映射
- [ ] `agents/content.py:CONTENT_PROMPTS` — 新 prompt 映射
- [ ] `ui/components/content_renderer.py` — 新渲染函式

缺一即標 FAIL。

### 5. 評估規範
- [ ] L1 / L2 metric 程式碼是否呼叫 LLM API？（不允許）
- [ ] L3 judge 模型清單是否維持跨廠商（OpenAI / Anthropic / Google）？

### 6. 危險模式（永遠標 FAIL）
- [ ] `try / except: pass` 吞掉 critic 或 structured output 例外
- [ ] 在 LangGraph node 內 hardcode 模型名 / API key
- [ ] 將 API key 印到 log（`logger.info(f"...api_key={key}...")`、`print(api_key)`）
- [ ] 移除 `iteration_count` 或 `content_node_retries` 上限檢查

## 輸出格式

開頭一行 verdict：`PASS` / `WARN` / `FAIL`
- **PASS**：所有檢查通過
- **WARN**：有可改善但非阻塞的問題（如資訊性建議）
- **FAIL**：至少一條違規。任何一條 FAIL → 整體 FAIL

接著按類別列出 findings，每條：

```
[FAIL] (類別) file:line — 規則名
  違規：<具體看到的問題>
  修法：<明確指令；引用 CLAUDE.md 對應條目>
```

範例：

```
[FAIL] (Schema 規範) src/coursegen/schemas.py:312 — content schema 第一欄位
  違規：`NewSummaryContent` 第一欄位是 `title: str`，不是 `reasoning: str`
  修法：在第一個欄位前插入 `reasoning: str = Field(description=_REASONING_DESC)`。
       見 CLAUDE.md「新增 / 修改 schema 時」第 1 條，及 `PrerequisiteContent` 範本。

[WARN] (LLM 呼叫) src/coursegen/agents/new_agent.py:42 — retry 上限 hardcode
  違規：寫死 `for _ in range(3):`
  修法：改從 `runtime.context.content_max_retries` 取；見 CLAUDE.md
       「呼叫 LLM / 取用設定時」第 2 條。
```

結尾若 PASS 給一句「全部規範通過，可以 commit」。

## 不要做的事

- 不要重複 ruff / ty 的工作（line length、unused import、type mismatch）
- 不要評論程式碼風格 / 命名 / 註解品質
- 不要提架構建議 / 重構意見（這是 sensor 不是 architect）
- 不要修檔 — 只報告，由人類或 AI 主程依 finding 修
