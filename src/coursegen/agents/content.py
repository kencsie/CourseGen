"""
Content Generation Agents

包含 5 個 LangGraph 節點函式：
1. content_planning_node     — 拓撲排序、初始化 State
2. content_knowledge_search_node — Per-node Tavily 搜尋
3. content_generation_node   — 根據節點類型生成教學內容
4. content_critic_node       — 審核生成的內容
5. content_advance_node      — 推進到下一個節點或結束

以及 1 個 Router 函式：
- content_router             — 決定下一步是 advance / retry / advance_with_failure
"""

import re
from collections import deque, defaultdict
from coursegen.schemas import (
    ContentState,
    ContextSchema,
    NodeType,
    ContentValidationResult,
    PrerequisiteContent,
    ConceptContent,
    PitfallContent,
    ComparisonContent,
    PracticeContent,
)
from coursegen.prompts.content import (
    CONTENT_PROMPTS,
    CONTENT_CRITIC_PROMPT,
    CONTENT_KNOWLEDGE_SYNTHESIS_PROMPT,
    SEARCH_QUERY_GENERATION_PROMPT,
)
from langgraph.runtime import Runtime
from langchain.chat_models import init_chat_model
from tavily import TavilyClient
import json
import logging

logger = logging.getLogger(__name__)

# ============================================================
# 節點類型 → Pydantic Model 查詢表
# ============================================================
CONTENT_MODELS = {
    "prerequisite": PrerequisiteContent,
    "concept": ConceptContent,
    "pitfall": PitfallContent,
    "comparison": ComparisonContent,
    "practice": PracticeContent,
}


# ============================================================
# Helper: 從 LLM 輸出文字中提取引用來源並重新編號
# ============================================================
def _extract_sources(result_dict: dict, raw_sources: list[dict]) -> dict:
    """從 LLM 輸出文字中提取引用編號，對照 raw_sources 建立 sources 清單並重新編號。"""

    def iter_strings(obj):
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, list):
            for item in obj:
                yield from iter_strings(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from iter_strings(v)

    # 排除 reasoning 欄位，只掃描實際內容中的引用
    content_only = {k: v for k, v in result_dict.items() if k != "reasoning"}
    all_text = " ".join(iter_strings(content_only))

    # 找出所有 [N] 引用，去重排序
    cited = sorted(set(int(m) for m in re.findall(r"\[(\d+)\]", all_text)))

    # 過濾有效的引用並建立 old→new 映射
    old_to_new = {}
    filtered_sources = []
    for old_idx in cited:
        src_idx = old_idx - 1  # [1] 對應 index 0
        if 0 <= src_idx < len(raw_sources):
            new_idx = len(filtered_sources) + 1
            old_to_new[old_idx] = new_idx
            s = raw_sources[src_idx]
            filtered_sources.append({
                "title": s["title"],
                "url": s["url"],
                "snippet": s.get("snippet", ""),
            })

    # 如果不需要重新編號（已經連續），跳過替換
    needs_renumber = any(old != new for old, new in old_to_new.items())

    if needs_renumber:
        def renumber(text):
            return re.sub(
                r"\[(\d+)\]",
                lambda m: f"[{old_to_new.get(int(m.group(1)), m.group(1))}]",
                text,
            )

        def map_strings(obj):
            if isinstance(obj, str):
                return renumber(obj)
            elif isinstance(obj, list):
                return [map_strings(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: map_strings(v) for k, v in obj.items()}
            return obj

        result_dict = {
            k: (map_strings(v) if k != "reasoning" else v)
            for k, v in result_dict.items()
        }

    result_dict["sources"] = filtered_sources
    return result_dict


# ============================================================
# Helper: 為 LLM invoke 構建帶識別資訊的 config
# ============================================================
def _make_llm_config(state: ContentState, step_name: str) -> dict:
    """Build RunnableConfig with content-node-specific run_name and metadata."""
    current_index = state["content_current_index"]
    current_node_id = state["content_order"][current_index]
    roadmap_nodes = {n["id"]: n for n in state["roadmap"]["nodes"]}
    current_node = roadmap_nodes[current_node_id]
    raw_type = current_node["type"]
    node_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)

    return {
        "run_name": f"[{current_index}] {current_node_id} ({node_type}) - {step_name}",
        "metadata": {
            "content_node_id": current_node_id,
            "content_node_type": node_type,
            "content_node_label": current_node["label"],
            "content_node_index": current_index,
            "step": step_name,
        },
    }


# ============================================================
# Node 1: content_planning_node
# ============================================================
def content_planning_node(state: ContentState, runtime: Runtime[ContextSchema]) -> dict:
    """
    拓撲排序 roadmap 節點，初始化 content generation 的 State 欄位。

    輸入：state["roadmap"] (dict with "nodes" list)
    輸出：content_order, content_current_index, content_map, content_failed_nodes
    """
    roadmap = state["roadmap"]
    nodes = roadmap["nodes"]

    graph = defaultdict(list)
    indegree = defaultdict(int)

    # 遍歷全部節點
    for node in nodes:
        # 建立有向圖
        for dependency in node["dependencies"]:
            if node["id"] not in graph[dependency]:
                graph[dependency].append(node["id"])

        # 建立indegree字典
        indegree[node["id"]] += len(node["dependencies"])

    topo_order = []
    queue = deque()

    # 處理indegree為0的節點
    for name, ind in indegree.items():
        if ind == 0:
            queue.append(name)

    # 依序處理，直到全部都遍歷為止
    while queue:
        name = queue.popleft()
        topo_order.append(name)

        # 節點的鄰居節點減一
        for neighbor in graph[name]:
            indegree[neighbor] -= 1

            # 減一後立即檢查
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    logger.info(f"拓撲排序完成，共 {len(topo_order)} 個節點: {topo_order}")

    return {
        "content_order": topo_order,
        "content_current_index": 0,
        "content_map": {},
        "content_failed_nodes": [],
        "content_node_retries": 0,
        "content_node_feedback": "",
        "content_node_knowledge": {},
    }


# ============================================================
# Node 2: content_knowledge_search_node
# ============================================================
def content_knowledge_search_node(
    state: ContentState, runtime: Runtime[ContextSchema]
) -> dict:
    """
    對當前節點進行 Tavily 搜尋，取得與節點類型相關的外部知識。

    參考：knowledge_search.py 中的 knowledge_search_node 實作模式。

    輸入：state["content_order"], state["content_current_index"], state["roadmap"]
    輸出：content_node_knowledge (dict with "synthesized_knowledge" key)
    """
    # 取得當前節點資訊
    current_index = state["content_current_index"]
    current_node_id = state["content_order"][current_index]
    roadmap_nodes = {n["id"]: n for n in state["roadmap"]["nodes"]}
    current_node = roadmap_nodes[current_node_id]

    node_label = current_node["label"]
    node_type = current_node["type"]

    logger.info(
        f"搜尋節點 [{current_index}] {current_node_id} ({node_type}): {node_label}"
    )

    if not runtime.context.tavily_api_key:
        logger.warning("TAVILY API KEY 不存在，跳過搜尋")
        return {"content_node_knowledge": {"synthesized_knowledge": ""}}

    # 用 LLM 生成搜尋 query（確保英文、簡潔、相關）
    topic = state["roadmap"]["topic"]

    model = init_chat_model(
        model=runtime.context.content_model,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0,
    )
    query_prompt = SEARCH_QUERY_GENERATION_PROMPT.format(
        topic=topic,
        node_type=node_type,
        label=node_label,
        description=current_node.get("description", ""),
    )
    query = model.invoke(query_prompt, config=_make_llm_config(state, "search_query")).content.strip()

    logger.info(f"搜尋 query: {query}")

    tavily_client = TavilyClient(api_key=runtime.context.tavily_api_key)

    try:
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            include_answer="advanced",
        )
    except Exception as e:
        logger.error(f"Tavily 搜尋失敗: {e}")
        return {"content_node_knowledge": {"synthesized_knowledge": ""}}

    answer = response.get("answer", "")
    logger.info(f"Tavily answer 長度: {len(answer)} 字")

    sources = [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("content", ""),
            "score": r.get("score", 0),
        }
        for r in response.get("results", [])
    ]
    logger.info(f"擷取 {len(sources)} 個來源片段")

    return {
        "content_node_knowledge": {
            "synthesized_knowledge": answer,
            "sources": sources,
        }
    }


# ============================================================
# Node 3: content_generation_node
# ============================================================
def content_generation_node(
    state: ContentState, runtime: Runtime[ContextSchema]
) -> dict:
    """
    根據節點類型，生成對應結構的教學內容。

    輸入：當前節點資訊、父節點摘要、外部知識、(可能的) critic feedback
    輸出：content_map (更新當前節點的內容)
    """
    # 取得當前節點資訊
    current_index = state["content_current_index"]
    current_node_id = state["content_order"][current_index]
    roadmap_nodes = {n["id"]: n for n in state["roadmap"]["nodes"]}
    current_node = roadmap_nodes[current_node_id]

    node_type = current_node["type"]
    topic = state["roadmap"]["topic"]

    logger.info(f"生成節點 [{current_index}] {current_node_id} ({node_type})")

    # 添加依賴節點的資訊
    parent_summaries = ""
    for node in current_node["dependencies"]:
        node_info = state["content_map"].get(node, "")
        parent_summaries += json.dumps(node_info, ensure_ascii=False, indent=2) + "\n\n"

    # 提取查找後的總結外部知識
    external_knowledge = state["content_node_knowledge"].get(
        "synthesized_knowledge", ""
    )

    # 格式化來源清單
    raw_sources = state["content_node_knowledge"].get("sources", [])
    sources_formatted = "\n\n".join(
        f"[{i+1}] {s['title']}\nURL: {s['url']}\n{s['snippet']}"
        for i, s in enumerate(raw_sources)
    ) or "（無來源資訊）"

    # 取得 critic feedback（重試時會有內容）
    critic_feedback = state.get("content_node_feedback", "")
    if critic_feedback:
        logger.info(f"重試中，附帶 critic 回饋: {critic_feedback[:100]}...")

    # 選擇與填寫要使用的prompt模板
    prompt_template = CONTENT_PROMPTS[node_type]
    prompt_template = prompt_template.format(
        topic=topic,
        user_preferences=state["user_preferences"],
        node_id=current_node_id,
        node_label=current_node["label"],
        node_description=current_node["description"],
        node_type=node_type,
        parent_summaries=parent_summaries,
        external_knowledge=external_knowledge,
        sources_formatted=sources_formatted,
        critic_feedback=critic_feedback or "（首次生成，無審核回饋）",
    )

    # 選擇要使用的回傳pydantic模型
    content_model = CONTENT_MODELS[node_type]

    # 呼叫 LLM
    model = init_chat_model(
        model=runtime.context.content_model,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0.1,
    )
    model_structured = model.with_structured_output(content_model)

    try:
        result = model_structured.invoke(prompt_template, config=_make_llm_config(state, "generation"))
    except Exception as e:
        logger.warning(f"Content generation LLM 呼叫失敗（截斷或解析錯誤）: {e}")
        result = None

    if result is None:
        return {
            "content_map": {},
            "content_node_feedback": "內容生成失敗（模型輸出截斷或 JSON 解析錯誤），需要重試。",
            "content_node_retries": state.get("content_node_retries", 0) + 1,
        }

    # 後處理：從 LLM 輸出中提取實際引用的來源
    content_dict = result.model_dump()
    content_dict = _extract_sources(content_dict, raw_sources)
    return {"content_map": {current_node_id: content_dict}}


# ============================================================
# Node 4: content_critic_node
# ============================================================
def content_critic_node(state: ContentState, runtime: Runtime[ContextSchema]) -> dict:
    """
    審核當前節點生成的教學內容。

    使用單一 critic model 進行審核，參考外部知識進行事實查核。

    輸入：當前節點的生成內容、外部知識
    輸出：content_node_feedback (str), 以及透過回傳值讓 router 判斷
    """
    current_index = state["content_current_index"]
    current_node_id = state["content_order"][current_index]
    roadmap_nodes = {n["id"]: n for n in state["roadmap"]["nodes"]}
    current_node = roadmap_nodes[current_node_id]

    logger.info(f"審核節點 [{current_index}] {current_node_id}")

    # 取得生成的內容
    content = state["content_map"].get(current_node_id, {})
    content_str = json.dumps(content, ensure_ascii=False, indent=2)

    # 取得外部知識
    knowledge = state.get("content_node_knowledge", {})
    external_knowledge = knowledge.get("synthesized_knowledge", "")

    # 格式化來源清單
    raw_sources = knowledge.get("sources", [])
    sources_formatted = "\n\n".join(
        f"[{i+1}] {s['title']}\nURL: {s['url']}\n{s['snippet']}"
        for i, s in enumerate(raw_sources)
    ) or "（無來源資訊）"

    # 格式化 critic prompt
    formatted_prompt = CONTENT_CRITIC_PROMPT.format(
        topic=state["roadmap"]["topic"],
        user_preferences=state["user_preferences"],
        node_label=current_node["label"],
        node_type=current_node["type"],
        node_description=current_node["description"],
        external_knowledge=external_knowledge or "（無外部知識）",
        sources_formatted=sources_formatted,
        content=content_str,
        previous_feedback=state.get("content_node_feedback", ""),
    )

    # 呼叫 LLM
    model = init_chat_model(
        model=runtime.context.content_model,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0,
    )
    model_structured = model.with_structured_output(ContentValidationResult)

    try:
        result = model_structured.invoke(formatted_prompt, config=_make_llm_config(state, "critic"))
    except Exception as e:
        logger.warning(f"Critic LLM 呼叫失敗（refusal 或解析錯誤）: {e}")
        result = None

    retries = state.get("content_node_retries", 0)

    if result is None:
        logger.warning("Critic 回傳 None，計入重試次數")
        return {
            "content_node_feedback": "Critic 無法審核此內容（模型拒絕或回傳空值），視為未通過。",
            "content_node_retries": retries + 1,
        }

    feedback_preview = (result.feedback or "")[:100]
    logger.info(
        f"審核結果: {'通過' if result.is_valid else '未通過'} | "
        f"回饋: {feedback_preview}..."
    )

    return {
        "content_node_feedback": result.feedback if not result.is_valid else "",
        "content_node_retries": retries + (0 if result.is_valid else 1),
    }


# ============================================================
# Router: content_router
# ============================================================
def content_router(state: ContentState, runtime: Runtime[ContextSchema]) -> str:
    """
    根據 critic 結果決定下一步：
    - "advance": 通過審核，前進到下一個節點
    - "retry": 未通過但還有重試機會，重新生成
    - "advance_with_failure": 未通過且超過重試上限，記錄失敗並前進

    回傳值會被 add_conditional_edges 使用。
    """
    feedback = state.get("content_node_feedback", "")
    retries = state.get("content_node_retries", 0)

    # feedback 為空 → critic 通過（content_critic_node 通過時清空 feedback）
    if not feedback:
        logger.info("路由: advance（通過審核）")
        return "advance"

    # 未通過，檢查重試次數
    if retries < runtime.context.content_max_retries:
        logger.info(
            f"路由: retry（重試 {retries}/{runtime.context.content_max_retries}）"
        )
        return "retry"

    logger.warning("路由: advance_with_failure（超過重試上限）")
    return "advance_with_failure"


# ============================================================
# Node 5: content_advance_node
# ============================================================
def content_advance_node(state: ContentState, runtime: Runtime[ContextSchema]) -> dict:
    """
    推進到下一個節點：
    - 更新 content_current_index
    - 重置 content_node_retries
    - 清空 content_node_knowledge 和 content_node_feedback
    - 如果是 advance_with_failure，記錄到 content_failed_nodes
    """
    current_index = state["content_current_index"]
    current_node_id = state["content_order"][current_index]
    next_index = current_index + 1
    total_nodes = len(state["content_order"])

    # 判斷是否為失敗推進
    feedback = state.get("content_node_feedback", "")
    retries = state.get("content_node_retries", 0)
    is_failure = bool(feedback) and retries >= runtime.context.content_max_retries

    result = {
        "content_current_index": next_index,
        "content_node_retries": 0,
        "content_node_feedback": "",
        "content_node_knowledge": {},
    }

    if is_failure:
        failed = list(state.get("content_failed_nodes", []))
        failed.append(current_node_id)
        result["content_failed_nodes"] = failed
        logger.warning(f"節點 {current_node_id} 標記為失敗")

    logger.info(f"推進: {current_node_id} 完成 ({next_index}/{total_nodes})")

    return result


# ============================================================
# Router: content_should_continue
# ============================================================
def content_should_continue(
    state: ContentState, runtime: Runtime[ContextSchema]
) -> str:
    """
    content_advance_node 之後的條件判斷：
    - "continue": 還有下一個節點，繼續搜尋 + 生成
    - "__end__": 所有節點都處理完了

    回傳值會被 add_conditional_edges 使用。
    """
    next_index = state["content_current_index"]
    total_nodes = len(state["content_order"])

    if next_index >= total_nodes:
        logger.info(
            f"所有節點處理完畢！"
            f"成功: {total_nodes - len(state.get('content_failed_nodes', []))}，"
            f"失敗: {len(state.get('content_failed_nodes', []))}"
        )
        return "__end__"
    else:
        return "continue"


# ============================================================
# 測試區域
# ============================================================
if __name__ == "__main__":
    mock_roadmap = {
        "topic": "Minecraft Java Edition 1.21.11 快速上手指南",
        "nodes": [
            {
                "id": "pre-check",
                "label": "版本環境診斷",
                "description": "確認已安裝 Java 版啟動器並能流暢運行 1.21.11，具備基礎生存與合成常識。",
                "type": "prerequisite",
                "dependencies": [],
            },
            {
                "id": "spear-basics",
                "label": "長矛戰鬥核心",
                "description": "學習長矛的合成表，並掌握「刺擊」與「衝鋒」兩種基礎攻擊模式的操作。",
                "type": "concept",
                "dependencies": ["pre-check"],
            },
            {
                "id": "mount-taming",
                "label": "新世代坐騎馴服",
                "description": "掌握鸚鵡螺與駱駝殭屍的馴服技巧，並學會裝備鞍與專屬鎧甲。",
                "type": "concept",
                "dependencies": ["pre-check"],
            },
            {
                "id": "spear-vs-sword",
                "label": "長矛 vs 劍：戰鬥取捨",
                "description": "比較長矛的距離優勢與劍的揮砍範圍，理解在不同地形下的武器選擇邏輯。",
                "type": "comparison",
                "dependencies": ["spear-basics"],
            },
            {
                "id": "charge-pitfall",
                "label": "衝鋒攻擊的常見誤區",
                "description": "避免在狹窄空間使用衝鋒導致撞牆受傷，並修正因移動速度不足導致的傷害低落。",
                "type": "pitfall",
                "dependencies": ["spear-basics"],
            },
            {
                "id": "underwater-exploration",
                "label": "水下探索實務",
                "description": "利用鸚鵡螺坐騎的「鸚鵡螺之息」效果，在不消耗氧氣的情況下進行水底神殿探索。",
                "type": "concept",
                "dependencies": ["mount-taming"],
            },
            {
                "id": "env-attributes-intro",
                "label": "環境屬性初探",
                "description": "了解 1.21.11 新增的環境規則，如霧氣顏色與光照對生物燃燒的影響。",
                "type": "concept",
                "dependencies": ["pre-check"],
            },
            {
                "id": "survival-challenge",
                "label": "綜合生存挑戰任務",
                "description": "在生存模式中合成一把長矛並馴服一隻鸚鵡螺，完成一次水下神殿的突襲行動。",
                "type": "practice",
                "dependencies": [
                    "spear-vs-sword",
                    "charge-pitfall",
                    "underwater-exploration",
                    "env-attributes-intro",
                ],
            },
        ],
    }

    # ==========================================================
    # 測試 1: content_planning_node（拓撲排序）
    # ==========================================================
    mock_state = {"roadmap": mock_roadmap}

    result = content_planning_node(mock_state, None)
    order = result["content_order"]

    print(f"拓撲排序結果: {order}")
    print(f"節點數量: {len(order)}")

    pos = {nid: i for i, nid in enumerate(order)}
    all_pass = True
    for node in mock_roadmap["nodes"]:
        for dep in node["dependencies"]:
            if pos.get(dep, -1) >= pos.get(node["id"], -1):
                print(
                    f"  FAIL: {dep} (pos={pos.get(dep)}) 應該在 {node['id']} (pos={pos.get(node['id'])}) 前面"
                )
                all_pass = False

    if all_pass:
        print("驗證通過！所有節點都在其 dependencies 之後。")
    else:
        print("驗證失敗，請檢查拓撲排序邏輯。")

    # ==========================================================
    # 測試 2: content_generation_node
    # ==========================================================
    # 模擬「前面幾個節點已經生成完」的狀態，測試不同情境

    # --- 已生成的父節點內容 (dummy) ---
    mock_content_map = {
        "pre-check": {
            # PrerequisiteContent
            "overview": "學習 Minecraft 1.21.11 前，你需要確認已安裝 Java 版啟動器並能正常運行遊戲。",
            "checklist": [
                "你能成功啟動 Minecraft Java Edition 嗎？",
                "你知道如何開啟生存模式並合成基本工具嗎？",
                "你了解基本的物品欄管理嗎？",
            ],
            "remediation": [
                "前往 minecraft.net 下載官方啟動器",
                "在創造模式中練習合成木鎬、石鎬等基礎工具",
            ],
        },
        "spear-basics": {
            # ConceptContent
            "explanation": "長矛是 1.21.11 新增的武器，擁有比劍更長的攻擊距離。合成方式為兩根木棍加一個鑽石...",
            "key_points": [
                "長矛攻擊距離為 3 格，比劍多 1 格",
                "刺擊模式適合單體目標，衝鋒模式適合群體",
                "衝鋒需要助跑 3 格以上才能觸發",
            ],
            "examples": [
                "在平原上對著殭屍使用衝鋒攻擊，可一擊造成 12 點傷害",
                "在礦洞中使用刺擊模式，安全距離攻擊骷髏",
            ],
        },
        "mount-taming": {
            # ConceptContent
            "explanation": "鸚鵡螺坐騎是 1.21.11 的重要新增內容，可在水下提供無限氧氣...",
            "key_points": [
                "鸚鵡螺出現在深海生態系",
                "馴服需要使用海帶餵食 3-5 次",
                "裝備鞍後可騎乘，水下移動速度提升 200%",
            ],
            "examples": [
                "在深海中找到鸚鵡螺後，手持海帶靠近並右鍵餵食",
            ],
        },
    }

    mock_knowledge = {
        "synthesized_knowledge": "長矛與劍的主要差異在於攻擊距離和傷害模式。劍的揮砍可對前方 180 度範圍造成 AOE 傷害，而長矛為直線單體攻擊但距離更遠..."
    }

    import os
    from dotenv import load_dotenv

    load_dotenv()

    class MockRuntime:
        class MockContext:
            content_model = "google/gemini-3-flash-preview"
            base_url = os.getenv("BASE_URL")
            openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
            content_max_retries = 3

        context = MockContext()

    print(f"\n{'=' * 60}")
    print("測試 content_generation_node")
    print(f"{'=' * 60}")

    # --- 情境 A: 有父節點的 comparison 節點 ---
    # spear-vs-sword 依賴 spear-basics（已在 content_map 中）
    test_state_a = {
        "roadmap": mock_roadmap,
        "user_preferences": "- Target Audience Level: BEGINNER\n- Learning Goal: QUICK_START\n- Preferred Language: Traditional Chinese (繁體中文)",
        "content_order": order,
        "content_current_index": order.index("spear-vs-sword"),
        "content_map": mock_content_map,
        "content_node_knowledge": mock_knowledge,
        "content_node_feedback": "",
        "content_node_retries": 0,
    }

    print(f"\n--- 情境 A: comparison 節點 (spear-vs-sword) ---")
    print(f"父節點: {mock_roadmap['nodes'][3]['dependencies']}")
    result_a = content_generation_node(test_state_a, MockRuntime())
    print(f"結果 keys: {list(result_a.get('content_map', {}).keys())}")
    if result_a.get("content_map", {}).get("spear-vs-sword"):
        print(
            json.dumps(
                result_a["content_map"]["spear-vs-sword"], ensure_ascii=False, indent=2
            )[:500]
        )
    else:
        print("未生成內容！請檢查實作。")

    # --- 情境 B: 多個父節點的 practice 節點（含失敗父節點）---
    # survival-challenge 依賴 4 個節點，但 env-attributes-intro 失敗了
    test_state_b = {
        "roadmap": mock_roadmap,
        "user_preferences": "- Target Audience Level: BEGINNER\n- Learning Goal: QUICK_START\n- Preferred Language: Traditional Chinese (繁體中文)",
        "content_order": order,
        "content_current_index": order.index("survival-challenge"),
        "content_map": mock_content_map,  # 只有 pre-check, spear-basics, mount-taming
        "content_node_knowledge": {"synthesized_knowledge": ""},
        "content_node_feedback": "",
        "content_node_retries": 0,
        "content_failed_nodes": ["env-attributes-intro"],
    }

    print(f"\n--- 情境 B: practice 節點 (survival-challenge), 有失敗的父節點 ---")
    print(f"父節點: {mock_roadmap['nodes'][7]['dependencies']}")
    print(f"失敗節點: {test_state_b['content_failed_nodes']}")
    result_b = content_generation_node(test_state_b, MockRuntime())
    print(f"結果 keys: {list(result_b.get('content_map', {}).keys())}")
    if result_b.get("content_map", {}).get("survival-challenge"):
        print(
            json.dumps(
                result_b["content_map"]["survival-challenge"],
                ensure_ascii=False,
                indent=2,
            )[:500]
        )
    else:
        print("未生成內容！請檢查實作。")

    # --- 情境 C: 無父節點的 prerequisite 節點 ---
    test_state_c = {
        "roadmap": mock_roadmap,
        "user_preferences": "- Target Audience Level: BEGINNER\n- Learning Goal: QUICK_START\n- Preferred Language: Traditional Chinese (繁體中文)",
        "content_order": order,
        "content_current_index": order.index("pre-check"),
        "content_map": {},
        "content_node_knowledge": {
            "synthesized_knowledge": "Minecraft Java Edition 需要安裝 Java Runtime Environment..."
        },
        "content_node_feedback": "",
        "content_node_retries": 0,
    }

    print(f"\n--- 情境 C: prerequisite 節點 (pre-check), 無父節點 ---")
    result_c = content_generation_node(test_state_c, MockRuntime())
    print(f"結果 keys: {list(result_c.get('content_map', {}).keys())}")
    if result_c.get("content_map", {}).get("pre-check"):
        print(
            json.dumps(
                result_c["content_map"]["pre-check"], ensure_ascii=False, indent=2
            )[:500]
        )
    else:
        print("未生成內容！請檢查實作。")
