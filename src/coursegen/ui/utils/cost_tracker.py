from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class CostTracker(BaseCallbackHandler):
    """Accumulate token usage and cost across all LLM calls in a LangGraph run."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self._cost_available = False
        self._seen_run_ids: set = set()

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        run_id = kwargs.get("run_id")
        if run_id is not None:
            if run_id in self._seen_run_ids:
                return
            self._seen_run_ids.add(run_id)

        for generation_list in response.generations:
            for generation in generation_list:
                msg = getattr(generation, "message", None)
                if msg is None:
                    continue

                # Token counts (standard LangChain UsageMetadata)
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)

                # Cost (OpenRouter-specific field in response_metadata)
                token_usage = msg.response_metadata.get("token_usage", {})
                cost = token_usage.get("cost") if isinstance(token_usage, dict) else None
                if isinstance(cost, (int, float)):
                    self.total_cost += cost
                    self._cost_available = True

    def get_summary(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "total_cost_usd": self.total_cost if self._cost_available else None,
        }
