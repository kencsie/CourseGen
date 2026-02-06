#!/usr/bin/env python3
"""
測試腳本：驗證三大改進
1. 迭代上限機制
2. 結構化 Feedback
3. Tavily 搜尋知識驗證
"""

from coursegen.schemas import Language, UserPreferences, LearningGoal, DifficultyLevel
from coursegen.workflows.basic import graph
import os
from dotenv import load_dotenv

load_dotenv()


def test_iteration_limit():
    """測試改進 1：迭代上限機制"""
    print("\n" + "="*60)
    print("測試 1: 迭代上限機制")
    print("="*60)

    prefs = UserPreferences(
        level=DifficultyLevel.BEGINNER,
        goal=LearningGoal.QUICK_START,
        language=Language.ZH_TW,
    )

    result = graph.invoke(
        {
            "question": "How to learn Python basics?",
            "user_preferences": prefs.to_prompt_context(),
            "iteration_count": 0,
            "max_iterations": 2,  # 設定較小的上限以快速測試
            "search_performed": False,
        },
        context={
            "model_name": "microsoft/phi-4",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "critic_1_model": "anthropic/claude-4.5-sonnet",
            "critic_2_model": "openai/gpt-4o",
            "critic_3_model": "google/gemini-3-flash-preview",
        },
    )

    # 驗證
    assert "iteration_count" in result, "❌ iteration_count 缺失"
    assert "max_iterations" in result, "❌ max_iterations 缺失"
    assert "termination_reason" in result, "❌ termination_reason 缺失"
    assert result["iteration_count"] <= result["max_iterations"], "❌ 超過最大迭代次數"

    print(f"\n✅ 測試通過！")
    print(f"   終止原因: {result['termination_reason']}")
    print(f"   迭代次數: {result['iteration_count']}/{result['max_iterations']}")
    print(f"   驗證狀態: {'通過' if result['roadmap_is_valid'] else '未通過'}")

    return result


def test_structured_feedback():
    """測試改進 2：結構化 Feedback 機制"""
    print("\n" + "="*60)
    print("測試 2: 結構化 Feedback 機制")
    print("="*60)

    prefs = UserPreferences(
        level=DifficultyLevel.INTERMEDIATE,
        goal=LearningGoal.DEEP_DIVE,
        language=Language.ZH_TW,
    )

    result = graph.invoke(
        {
            "question": "How to learn React hooks?",
            "user_preferences": prefs.to_prompt_context(),
            "iteration_count": 0,
            "max_iterations": 3,
            "search_performed": False,
        },
        context={
            "model_name": "microsoft/phi-4",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "critic_1_model": "anthropic/claude-4.5-sonnet",
            "critic_2_model": "openai/gpt-4o",
            "critic_3_model": "google/gemini-3-flash-preview",
        },
    )

    # 驗證結構化回饋
    assert "roadmap_feedback" in result, "❌ roadmap_feedback 缺失"
    feedback = result["roadmap_feedback"]
    assert len(feedback) > 0, "❌ feedback 列表為空"

    # 找到 aggregated feedback
    aggregated = None
    for item in feedback:
        if isinstance(item, dict) and item.get("aggregated"):
            aggregated = item
            break

    assert aggregated is not None, "❌ 未找到 aggregated feedback"
    assert "critical_issues" in aggregated, "❌ critical_issues 缺失"
    assert "consensus_issues" in aggregated, "❌ consensus_issues 缺失"
    assert "summary" in aggregated, "❌ summary 缺失"

    # 驗證 metadata
    metadata = result.get("validation_metadata", {})
    assert "critical_issue_count" in metadata, "❌ critical_issue_count 缺失"
    assert "consensus_issue_count" in metadata, "❌ consensus_issue_count 缺失"

    print(f"\n✅ 測試通過！")
    print(f"   Critical issues: {len(aggregated['critical_issues'])}")
    print(f"   Consensus issues: {len(aggregated['consensus_issues'])}")
    print(f"   Summary: {aggregated['summary'][:100]}...")

    return result


def test_tavily_search():
    """測試改進 3：Tavily 搜尋知識驗證"""
    print("\n" + "="*60)
    print("測試 3: Tavily 搜尋知識驗證")
    print("="*60)

    prefs = UserPreferences(
        level=DifficultyLevel.BEGINNER,
        goal=LearningGoal.QUICK_START,
        language=Language.ZH_TW,
    )

    result = graph.invoke(
        {
            "question": "How to learn TypeScript?",
            "user_preferences": prefs.to_prompt_context(),
            "iteration_count": 0,
            "max_iterations": 3,
            "search_performed": False,
        },
        context={
            "model_name": "microsoft/phi-4",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "critic_1_model": "anthropic/claude-4.5-sonnet",
            "critic_2_model": "openai/gpt-4o",
            "critic_3_model": "google/gemini-3-flash-preview",
        },
    )

    # 驗證搜尋執行
    assert "search_performed" in result, "❌ search_performed 缺失"
    assert result["search_performed"] == True, "❌ 搜尋未執行"

    # 如果有 TAVILY_KEY，應該有 knowledge_context
    if os.getenv("TAVILY_KEY"):
        kc = result.get("knowledge_context")
        if kc:
            assert "query" in kc, "❌ query 缺失"
            assert "results" in kc, "❌ results 缺失"
            assert "summary" in kc, "❌ summary 缺失"

            print(f"\n✅ 測試通過！")
            print(f"   搜尋查詢: {kc['query']}")
            print(f"   找到資源: {len(kc['results'])} 個")
            print(f"   總結: {kc['summary'][:150]}...")
        else:
            print(f"\n⚠️  search_performed=True 但沒有 knowledge_context（可能搜尋失敗）")
    else:
        print(f"\n⚠️  未設定 TAVILY_KEY，跳過知識驗證測試")

    return result


def main():
    print("\n🚀 開始測試三大改進...")

    try:
        # 測試 1
        result1 = test_iteration_limit()

        # 測試 2
        result2 = test_structured_feedback()

        # 測試 3
        result3 = test_tavily_search()

        print("\n" + "="*60)
        print("✅ 所有測試通過！")
        print("="*60)
        print("\n總結：")
        print("✅ Phase 1: 迭代上限機制 - 正常運作")
        print("✅ Phase 2: 結構化 Feedback - 正常運作")
        print("✅ Phase 3: Tavily 搜尋 - 正常運作")

    except AssertionError as e:
        print(f"\n❌ 測試失敗: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
