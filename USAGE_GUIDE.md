# CourseGen 使用指南 - 三大改進功能

## 快速開始

### 基本執行
```bash
# 運行主 workflow
python -m src.coursegen.workflows.basic

# 運行 Streamlit UI
streamlit run src/coursegen/ui/app.py
```

---

## 功能 1: 迭代上限控制

### 調整最大迭代次數

```python
from coursegen.workflows.basic import graph

result = graph.invoke(
    {
        "question": "How to learn Python?",
        "user_preferences": prefs.to_prompt_context(),
        "iteration_count": 0,
        "max_iterations": 5,  # 👈 自定義最大迭代次數（默認3）
        "search_performed": False,
    },
    context={...}
)

# 檢查終止原因
print(result["termination_reason"])
# 輸出: "validation_passed" 或 "max_iterations_reached"
```

### 理解輸出

```bash
✅ 終止原因: validation_passed
📊 迭代次數: 2/5
🎯 驗證狀態: 通過
```

- **validation_passed**: roadmap 通過驗證（2/3+ critics 同意）
- **max_iterations_reached**: 達到上限但仍未通過（接受當前版本）

### 最佳實踐

| 情境 | 推薦 max_iterations | 原因 |
|------|-------------------|------|
| 快速測試 | 1-2 | 節省 API calls |
| 一般使用 | 3 (默認) | 平衡品質與成本 |
| 高品質需求 | 5-7 | 追求最佳結果 |
| 簡單主題 | 2-3 | 通常第一次就通過 |
| 複雜主題 | 4-6 | 需要更多迭代 |

---

## 功能 2: 結構化 Feedback

### 查看結構化問題

```python
# 取得結果
result = graph.invoke(...)

# 查看所有 feedback
feedback = result["roadmap_feedback"]

# 找到整合後的結構化 feedback
aggregated = [f for f in feedback if f.get("aggregated")][0]

# 查看 critical issues
for issue in aggregated["critical_issues"]:
    print(f"類型: {issue['issue_type']}")
    print(f"嚴重度: {issue['severity']}")
    print(f"位置: {issue['location']}")
    print(f"描述: {issue['description']}")
    print(f"建議: {issue['suggested_fix']}")
    print("---")

# 查看共識問題（2+ critics 同意）
for issue in aggregated["consensus_issues"]:
    print(f"共識問題: {issue['issue_type']} @ {issue['location']}")

# 查看總結
print(f"總結: {aggregated['summary']}")
```

### 問題類型參考

| 類型 | 說明 | 範例 |
|------|------|------|
| `missing_node_type` | 缺少特定類型的節點 | 沒有「踩雷」節點 |
| `invalid_dependency` | 無效的依賴關係 | 依賴不存在的節點 |
| `circular_dependency` | 循環依賴 | A→B→C→A |
| `wrong_difficulty` | 難度不符 | Beginner 用了高級概念 |
| `wrong_goal` | 目標不符 | Quick Start 太深入 |
| `wrong_language` | 語言不符 | 應該中文但用英文 |
| `poor_description` | 描述不清楚 | 太模糊或太簡短 |
| `hallucinated_content` | 編造內容 | 不存在的工具/術語 |
| `granularity_issue` | 顆粒度問題 | 節點太多或太少 |
| `linear_structure` | 過於線性 | 沒有分支，只有 1→2→3 |

### 嚴重度分級

- **critical** - 必須修正，否則 roadmap 無法使用
- **major** - 影響品質，強烈建議修正
- **minor** - 小問題，可選修正

### Metadata 統計

```python
metadata = result["validation_metadata"]

print(f"通過票數: {metadata['valid_votes']}/3")
print(f"共識級別: {metadata['consensus_level']}")  # unanimous / majority
print(f"嚴重問題數: {metadata['critical_issue_count']}")
print(f"共識問題數: {metadata['consensus_issue_count']}")
```

---

## 功能 3: Tavily 搜尋知識驗證

### 設定 Tavily API Key

```bash
# 在 .env 文件中
TAVILY_KEY=your_tavily_api_key_here
```

### 查看搜尋結果

```python
result = graph.invoke(...)

# 檢查是否執行搜尋
if result["search_performed"]:
    kc = result.get("knowledge_context")

    if kc:
        # 搜尋查詢
        print(f"搜尋查詢: {kc['query']}")

        # 關鍵發現總結
        print(f"關鍵發現:\n{kc['summary']}")

        # 資料來源
        for result in kc['results']:
            print(f"標題: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"相關性: {result['score']}")
            print(f"內容摘要: {result['content'][:200]}...")
            print("---")
```

### 搜尋優化技巧

搜尋查詢自動優化：
```python
# 原始問題
"How to learn React hooks?"

# 自動轉換為
"react hooks tutorial guide 2024 2025 2026"
```

關鍵字自動添加：
- ✅ "tutorial" - 尋找教學資源
- ✅ "guide" - 尋找指南
- ✅ "2024 2025 2026" - 確保最新資訊

### 沒有 Tavily Key 的情況

```bash
⚠️  未設定 TAVILY_KEY，跳過知識搜尋
```

系統會：
- ✅ 優雅降級，使用 LLM 內部知識
- ✅ 不影響正常運行
- ✅ 仍然生成高品質 roadmap

### 搜尋失敗處理

如果搜尋 API 失敗：
```bash
⚠️  搜尋失敗: [錯誤訊息]，繼續使用 LLM 內部知識
```

系統會：
- ✅ 捕獲錯誤
- ✅ 記錄警告
- ✅ 繼續執行（不中斷）

---

## 組合使用範例

### 範例 1: 高品質模式（所有功能啟用）

```python
result = graph.invoke(
    {
        "question": "How to learn machine learning?",
        "user_preferences": UserPreferences(
            level=DifficultyLevel.BEGINNER,
            goal=LearningGoal.DEEP_DIVE,
            language=Language.ZH_TW,
        ).to_prompt_context(),
        "iteration_count": 0,
        "max_iterations": 5,  # 允許更多迭代
        "search_performed": False,
    },
    context={
        "model_name": "anthropic/claude-4.5-sonnet",  # 高品質模型
        "base_url": os.getenv("BASE_URL"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "critic_1_model": "anthropic/claude-4.5-sonnet",
        "critic_2_model": "openai/gpt-4o",
        "critic_3_model": "google/gemini-3-flash-preview",
    },
)

# 分析結果
print(f"🔍 搜尋: {len(result['knowledge_context']['results'])} 個資源")
print(f"📊 迭代: {result['iteration_count']}/{result['max_iterations']}")
print(f"✅ 終止: {result['termination_reason']}")

# 查看結構化問題
feedback = [f for f in result["roadmap_feedback"] if f.get("aggregated")][0]
print(f"🚨 嚴重問題: {len(feedback['critical_issues'])}")
print(f"🤝 共識問題: {len(feedback['consensus_issues'])}")
```

### 範例 2: 快速模式（成本優化）

```python
result = graph.invoke(
    {
        "question": "How to learn Python basics?",
        "user_preferences": UserPreferences(
            level=DifficultyLevel.BEGINNER,
            goal=LearningGoal.QUICK_START,
            language=Language.ZH_TW,
        ).to_prompt_context(),
        "iteration_count": 0,
        "max_iterations": 2,  # 限制迭代
        "search_performed": False,
    },
    context={
        "model_name": "microsoft/phi-4",  # 較便宜的模型
        "base_url": os.getenv("BASE_URL"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "critic_1_model": "anthropic/claude-3.5-sonnet",
        "critic_2_model": "openai/gpt-4o-mini",  # 便宜的 critic
        "critic_3_model": "google/gemini-3-flash-preview",
    },
)
```

### 範例 3: 調試模式（詳細輸出）

```python
import json

result = graph.invoke(...)

# 完整輸出所有資訊
print("\n=== 完整結果 ===")
print(json.dumps({
    "roadmap": result["roadmap"],
    "iteration_count": result["iteration_count"],
    "max_iterations": result["max_iterations"],
    "termination_reason": result["termination_reason"],
    "validation_metadata": result["validation_metadata"],
    "search_performed": result["search_performed"],
    "knowledge_context": result.get("knowledge_context"),
    "roadmap_feedback": result["roadmap_feedback"],
}, indent=2, ensure_ascii=False))
```

---

## 性能優化建議

### Token 成本優化

1. **調整迭代次數**
   ```python
   max_iterations = 2  # 簡單主題
   max_iterations = 3  # 一般主題（默認）
   max_iterations = 5  # 複雜主題
   ```

2. **選擇合適的模型**
   ```python
   # 便宜但快速
   model_name = "microsoft/phi-4"
   critic_2_model = "openai/gpt-4o-mini"

   # 高品質但昂貴
   model_name = "anthropic/claude-4.5-sonnet"
   critic_2_model = "openai/gpt-4o"
   ```

3. **有選擇地使用搜尋**
   ```python
   # 對於已知主題，可以跳過搜尋
   if is_well_known_topic:
       result = graph.invoke({
           ...,
           "search_performed": True,  # 標記為已搜尋（跳過）
           "knowledge_context": None,
       })
   ```

### 延遲優化

1. **並行 Critic 已默認啟用**
   - 3個 critics 並行執行
   - 自動由 LangGraph 處理

2. **Tavily 搜尋只執行一次**
   - 在 workflow 開始時執行
   - 結果在整個 loop 中重複使用

---

## 故障排除

### 問題 1: 搜尋一直失敗

**症狀**: `⚠️  搜尋失敗` 每次都出現

**解決方案**:
1. 檢查 TAVILY_KEY 是否正確
   ```bash
   echo $TAVILY_KEY
   ```
2. 檢查 API 配額
   - 訪問 Tavily 控制台查看剩餘配額
3. 暫時禁用搜尋
   ```python
   # 在 .env 中註解掉
   # TAVILY_KEY=...
   ```

### 問題 2: 迭代一直不通過

**症狀**: 達到 max_iterations 但仍未通過

**解決方案**:
1. 增加 max_iterations
2. 查看結構化 feedback 找出反覆出現的問題
3. 檢查是否是模型能力問題（換更強的模型）
4. 檢查主題是否太複雜（簡化問題）

### 問題 3: 結構化 feedback 解析失敗

**症狀**: aggregated feedback 中缺少 issues

**解決方案**:
1. 檢查 critic 模型是否支援 structured output
2. 查看原始 feedback（非 aggregated 部分）
3. 降級使用舊版 ROADMAP_CRITIC_PROMPT（如果需要）

---

## API Reference

### State 字段

| 字段 | 類型 | 說明 |
|------|------|------|
| `question` | str | 使用者問題 |
| `user_preferences` | str | 使用者偏好 |
| `roadmap` | dict | 生成的 roadmap |
| `critics` | list[dict] | Critic 結果列表 |
| `roadmap_feedback` | list[dict] | 整合的 feedback |
| `roadmap_is_valid` | bool | 是否通過驗證 |
| `validation_metadata` | dict | 驗證元數據 |
| `iteration_count` | int | 當前迭代次數 |
| `max_iterations` | int | 最大迭代次數 |
| `termination_reason` | str | 終止原因 |
| `knowledge_context` | dict | 外部知識上下文 |
| `search_performed` | bool | 是否已執行搜尋 |

### Context Schema 參數

| 參數 | 類型 | 默認值 | 說明 |
|------|------|--------|------|
| `model_name` | str | - | 主生成模型 |
| `base_url` | str | - | API base URL |
| `openrouter_api_key` | str | - | API key |
| `critic_1_model` | str | claude-3.5-sonnet | Critic 1 模型 |
| `critic_2_model` | str | gpt-4o | Critic 2 模型 |
| `critic_3_model` | str | gemini-2.5-flash | Critic 3 模型 |
| `max_iterations` | int | 3 | 最大迭代次數 |

---

## 常見問題 FAQ

### Q: 為什麼有時候第一次就通過，有時候需要3次？

**A**: 取決於：
- 主題複雜度（簡單主題更容易通過）
- 模型能力（更強的模型更容易一次通過）
- Critic 嚴格程度（3個 critics 中至少2個同意）
- 是否有外部知識（有搜尋結果時更準確）

### Q: 結構化 feedback 比原始 feedback 好在哪裡？

**A**:
- ✅ **可操作性**: 每個問題都有具體修正建議
- ✅ **優先級**: 區分 critical/major/minor
- ✅ **共識**: 找出多個 critics 都同意的問題
- ✅ **結構化**: 機器可讀，易於分析和優化

### Q: Tavily 搜尋會增加多少成本？

**A**:
- Tavily API: ~$0.005 per search (advanced mode)
- LLM 總結: ~$0.001 (使用 gpt-4o-mini)
- 總成本增加: ~$0.006 per roadmap generation
- 但能顯著提升準確性，減少幻覺

### Q: 可以只用其中一個或兩個改進嗎？

**A**: 可以，但不推薦：
- 三個改進設計為互相增強
- 迭代上限是基礎安全保障（必須）
- 結構化 feedback 提升效率（強烈建議）
- Tavily 搜尋提升準確性（可選，但推薦）

### Q: 如何在 Streamlit UI 中使用這些功能？

**A**: UI 已自動整合所有改進：
- 迭代上限自動生效
- 結構化 feedback 會在內部使用
- Tavily 搜尋會在背景執行
- 使用者無需額外配置

---

## 更多資源

- **實作總結**: 查看 `IMPLEMENTATION_SUMMARY.md`
- **測試腳本**: 運行 `test_improvements.py`
- **專案文檔**: 查看 `CLAUDE.md`
- **設定指南**: 查看 `SETUP_GUIDE.md`

---

**版本**: v2.0
**更新日期**: 2026-02-06
