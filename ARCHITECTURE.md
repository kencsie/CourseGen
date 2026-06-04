# CourseGen — ARCHITECTURE

本檔記錄「內部怎麼接、為什麼這樣接」（與 README 的使用者面、CLAUDE.md 的程式碼地圖互補）。
它隨架構決策**逐漸長大**，不求一次寫完。

## 節點型別系統（node types）

教學內容有 5 種節點型別：`prerequisite` / `concept` / `pitfall` / `comparison` / `practice`
（真相來源：`src/coursegen/schemas.py` 的 `NodeType`）。

**設計想法**：節點型別是系統的「一級概念」。每種型別的行為**散在 5 個協調的登記點**：

| 登記點 | 角色 |
|---|---|
| `schemas.py`（Content model class） | 該型別的資料結構 |
| `prompts/content.py:CONTENT_PROMPTS` | 生成用的 prompt |
| `agents/content.py:CONTENT_MODELS` | 型別 → schema 的查詢表 |
| `agents/content.py`（生成節點） | 透過上面兩張表取 model / prompt |
| `ui/components/content_renderer.py:_RENDERERS` | 該型別怎麼畫到畫面上 |

**為什麼要五處同步**：少登記一處 = 半套。最典型是「schema 加了、`_RENDERERS` 忘了」——
程式不當場報錯，直到使用者點開該型別節點才**靜默失敗**。這種「漏一處、之後才爆」最難抓。

**怎麼保證**：`tests/test_content_type_registry.py`——以 `NodeType` 為真相來源，
比對 `CONTENT_MODELS` / `CONTENT_PROMPTS` / `_RENDERERS` 三張表的鍵是否一致。
新增型別卻漏掉某表 → 對應那條測試立刻變紅、指出是哪張表。
（綠燈＝此刻五處一致的**證明**，取代了「請記得改五處」這句無法驗證的散文。）
