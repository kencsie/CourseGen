#!/bin/bash
# Steering Loop sensor chain — Stop hook for CourseGen
# 依序跑 ruff → pytest（若有測試）。任一失敗則 block AI 結束 turn，
# 把錯誤訊息塞回 additionalContext 強迫 AI 繼續修。
#
# 設計參考：CLAUDE.md「開發要點 > 工作流程（Steering Loop）」
# Inferential sensor（code-review skill）維持手動 `/code-review` 觸發，不綁進這裡。
# ty 仍在 preview 階段，library type stub 噪音大，目前不納入 hook（可手動 `uv run ty check src/`）。

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 0

FAILURES=""

# ── [1/2] Ruff lint ──────────────────────────────────────────────────
echo "[1/2] Ruff..."
if ! RUFF_OUT=$(uv run ruff check src/ 2>&1); then
  FAILURES="${FAILURES}━━━ RUFF FAILED ━━━
${RUFF_OUT}

修法：對個別違規逐條修正；若是 legacy / library 限制，加 per-file-ignore 到 pyproject.toml。

"
fi

# ── [2/2] pytest（偵測到測試才跑） ───────────────────────────────────
echo "[2/2] pytest..."
if [ -d "tests" ] || find . -maxdepth 4 \( -path ./.venv -o -path ./.git \) -prune -o -name "test_*.py" -print 2>/dev/null | grep -q .; then
  if ! PYTEST_OUT=$(uv run pytest 2>&1); then
    FAILURES="${FAILURES}━━━ PYTEST FAILED ━━━
${PYTEST_OUT}

修法：依測試輸出修正；若新增的程式碼缺對應測試，補上。

"
  fi
else
  echo "  ⊘ 未偵測到 test 檔，略過"
fi

# ── 報告結果 ─────────────────────────────────────────────────────────
if [ -z "$FAILURES" ]; then
  echo "✓ Steering Loop 全部通過"
  exit 0
fi

# block AI 結束 turn，把錯誤訊息塞進 additionalContext
jq -n --arg failures "$FAILURES" '{
  "decision": "block",
  "reason": "Steering Loop validation failed",
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": $failures
  }
}'
exit 2
