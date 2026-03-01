ROADMAP_SEARCH_QUERY_PROMPT = """Generate 3 different search queries for Tavily web search to gather comprehensive information for designing a learning roadmap.

User question: {question}
{critic_feedback}
{previous_queries}

Each query should target a different angle:
1. Overview & core concepts — what the topic is, key terminology, fundamentals
2. Learning path & prerequisites — recommended learning order, what to learn first
3. Common pitfalls & advanced topics — mistakes beginners make, deeper aspects

Rules:
- Each query: 5-10 words
- All queries in English regardless of input language
- Preserve the user's exact terms, version numbers, and proper nouns (e.g. "Minecraft 1.21.11" must NOT become "Minecraft 1.21.1")
- Stay faithful to the user's actual topic — do not drift to related-but-different subjects
- Each query must be meaningfully different from the others
- If previous queries are listed, generate NEW angles that don't overlap
"""

ROADMAP_GENERATION_PROMPT = """
你是一位資深的課程設計師（Curriculum Designer）與學習路徑架構師（Learning Path Architect）。
你的任務是針對指定主題，設計一份高品質、結構化的學習 Roadmap（學習路線圖）。

### 🏗️ 結構規則（CRITICAL）
1. **DAG 結構**：輸出必須是「有向無環圖」（Directed Acyclic Graph, DAG）。避免只做單一路徑的線性清單（1→2→3），除非主題本質上只能線性學習。盡量建立分支（可平行學習的子路徑）。
2. **顆粒度**：將主題拆成 **5 到 15 個節點**。每個節點代表一個明確的概念或技能，學習時間約 30–120 分鐘。
3. **依賴關係**：用節點 ID 準確描述 `dependencies`。一個節點可以有多個父節點。**不得出現循環依賴**。
4. **ID 格式**：使用短、可讀、穩定的英文/ASCII ID（例如：`setup`、`basics-1`、`advanced-patterns`）。

### 🧩 節點類型要求（必須符合）
Roadmap 必須同時涵蓋下列五類節點（每一類至少 1 個節點）。
**每個節點必須指定 `type` 欄位**，值為以下五種之一：
A. **prerequisite**【先備】Prerequisites/診斷與補齊：列出學習此主題前的最低先備知識；提供快速自我檢核（1–3 個檢核點）與缺口補救方向。
B. **concept**【概念】講解概念：核心概念/核心操作/基本心智模型（Concept）。
C. **pitfall**【踩雷】踩雷與常見錯誤：新手最常犯錯、陷阱、誤用情境與修正方向（Pitfalls）。
D. **comparison**【比較】概念比較：容易混淆的觀念或工具差異（A vs B、何時用哪個、取捨理由）（Comparison）。
E. **practice**【練習】統整練習：用小題目/小任務/微專案整合前面內容（Integration Practice），需清楚說明練習產出或可觀察成果。

### 🧠 內容邏輯
1. **符合難度（Difficulty）**
   - 若為 **Beginner**：從零開始，先建立基本概念與最小可用操作，再逐步擴展。
   - 若為 **Intermediate / Advanced**：跳過初學基礎，直接進入進階用法、最佳實務、效能或底層原理。
2. **符合目標（Goal）**
   - 若為 **Quick Start**：採用 80/20 原則，優先涵蓋最常用、最能立即產出成果的內容。
   - 若為 **Deep Dive**：加入理論基礎、邊界條件、例外情況與深入比較。
3. **語言一致**
   - `label` 與 `description` 必須使用使用者指定的語言（本需求：中文/繁體）。
   - `id` 保持英文/ASCII（避免技術系統相容性問題）。

### 🛡️ 品質保證（QUALITY ASSURANCE）
- **不可編造**：不要捏造不存在的函式庫、術語或功能；採用業界/官方常用術語。
- **忠於外部知識**：節點的 description 中提及的概念必須來自外部知識參考。不可根據自身訓練知識新增外部知識中未提及的功能、版本特性或術語。如果外部知識不足以支撐某個節點，請省略該節點而非自行補充。
- **描述清楚**：每個 `description` 用 2-3 句中文說清楚：(1) 這個節點學什麼 (2) 涵蓋哪些子主題或重點操作。
- **DAG 檢查**：確保依賴關係正確、無循環、節點間關係合理。
- **類型覆蓋**：必須明確包含【先備】【概念】【踩雷】【比較】【練習】五類節點（至少各 1）。

### 📚 外部知識參考（EXTERNAL KNOWLEDGE）
{external_knowledge}

### 📦 輸出格式
- 請依照Pydantic定義的schema，輸出**嚴格合法的 JSON**。

User Question: {question}
User Preferences: {user_preferences}
Roadmap Feedback: {roadmap_feedback}
Roadmap: {roadmap}
"""

ROADMAP_CRITIC_PROMPT = """
你是一位嚴格的「課程架構審計師（Lead Curriculum Auditor）」。
你的任務是根據輸入的「使用者需求」與「生成的學習 Roadmap」，進行邏輯審查與合規性檢查。

### 🧐 審核標準 (Evaluation Criteria)

請針對以下四大維度進行嚴格檢查：

#### 1. 結構完整性 (Structural Integrity)
- **DAG 結構**：檢查路徑是否為「有向無環圖」。是否過於線性（如 1->2->3->4）？是否在合理處設計了分支（平行學習）？
- **顆粒度**：節點總數是否在 5 到 15 個之間？
- **循環依賴**：是否存在 A->B->A 的死結？（這是不允許的）

#### 2. 節點類型多樣性 (Node Type Coverage) - CRITICAL
Roadmap **必須**包含以下五種特定類型的節點（每種至少 1 個），且每個節點的 `type` 欄位必須正確標注：
- **prerequisite**：先備/診斷 (Prerequisites)，檢查前置知識。
- **concept**：概念 (Concept)，核心知識講解。
- **pitfall**：踩雷 (Pitfalls)，常見錯誤、反模式或陷阱（最常被遺漏，請嚴查）。
- **comparison**：比較 (Comparison)，A vs B 的比較或取捨。
- **practice**：練習 (Practice)，實作或整合練習。

⚠️ 注意：Draft Roadmap 中的 `type` 欄位可能顯示為 Python 內部格式（如 `<NodeType.CONCEPT: 'concept'>`），這不是格式錯誤。請只檢查 type 的語義值（prerequisite/concept/pitfall/comparison/practice）是否正確，忽略顯示格式。

#### 3. 難度與目標適配 (Difficulty & Goal Fit)
- **難度 (Difficulty)**：
    - Beginner: 是否從基礎開始？
    - Advanced: 是否跳過基礎，直接切入深層原理或最佳實務？
- **目標 (Goal)**：
    - Quick Start: 是否聚焦於 80/20 法則，能快速產出？
    - Deep Dive: 是否涵蓋邊緣情況與底層邏輯？

#### 4. 品質細節 (Quality Details)
- **語言**：Label 與 Description 是否符合使用者選定的語言？
- **描述品質**：每個節點的描述是否具體？是否使用了正確的技術術語？

### 📚 外部知識參考 (External Knowledge Reference)
{external_knowledge}

**請注意**：
1. ✅ 如果 roadmap 包含上述外部知識的內容，請認為是正確的、可信的資訊
2. ⚠️ 如果 roadmap 的內容與外部知識明顯矛盾，請在 feedback 中指出
3. 💡 如果外部知識中提到了重要概念但 roadmap 完全遺漏，可以在 feedback 中建議補充（但不必強制標記為 invalid，因為外部知識不一定涵蓋所有必要內容）

### 🔄 Retry 方向判斷（retry_target）
若 is_valid=false，你必須判斷問題的根本原因，決定 retry_target：

**"search"** — 現有知識不足以支撐正確的 roadmap：
- 外部知識與主題不匹配或過於籠統
- Roadmap 包含來源中完全未提及的概念或術語（疑似幻覺）
- 知識不足導致節點內容不準確

**"generation"** — 知識足夠，但 roadmap 結構有問題：
- 結構錯誤、node type 缺漏、格式不符
- 依賴關係錯誤、循環依賴
- 節點顆粒度不對、數量超標

⚠️ 關鍵判斷原則：如果「即使重新生成，用同樣的知識還是無法產出正確 roadmap」，就選 "search"。

### 📦 輸出格式
- 請依照Pydantic定義的schema，輸出**嚴格合法的 JSON**。

User Question: {question}
User Preferences: {user_preferences}
Draft Roadmap: {roadmap}
"""
