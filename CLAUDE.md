# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CourseGen is an AI agent-based automated course roadmap generation system. It uses LangGraph to orchestrate a self-correcting agent loop: a generator agent creates learning roadmaps as DAGs, and a critic agent validates them, looping back with feedback until the roadmap passes validation.

## Development Commands

```bash
# Install dependencies (requires uv)
uv sync

# Run the Streamlit UI (recommended)
streamlit run src/coursegen/ui/app.py
# Or use the convenience script:
./scripts/run_ui.sh

# Run the main workflow (CLI)
python -m src.coursegen.workflows.basic

# Run Jupyter notebooks for interactive testing
uv run jupyter lab
# Notebooks are in notebook/ (student_test.ipynb, teacher_test.ipynb)
```

There is no test suite, linter, or CI/CD configured.

## Architecture

The system implements a **Generator-Critic loop** via LangGraph's `StateGraph`:

```
START → roadmap_node → roadmap_critic_node ⟲ (loops back with feedback if invalid)
                              ↓ (valid)
                             END
```

### Key source layout under `src/coursegen/`:

#### Core Engine
- **`schemas.py`** — Pydantic models defining the LangGraph `State`, `UserPreferences` (difficulty level, learning goal, language), `RoadmapNode`, `Roadmap`, and `RoadmapValidationResult`. The State flows through the entire graph.
- **`agents/roadmap.py`** — Two LangGraph node functions: `roadmap_node` (generates structured `Roadmap` via LLM) and `roadmap_critic_node` (validates the roadmap and produces feedback). Both use `model.with_structured_output()` for Pydantic-enforced responses.
- **`prompts/roadmap.py`** — `ROADMAP_GENERATION_PROMPT` and `ROADMAP_CRITIC_PROMPT`. The generation prompt enforces DAG structure, 5-15 node granularity, and adapts to user level/goal/language. The critic prompt checks DAG validity, relevance, hallucinations, and language compliance.
- **`workflows/basic.py`** — LangGraph `StateGraph` definition with conditional edges. This is the entry point (`python -m`).
- **`utils/tavily_search.py`** — Tavily search wrapper (currently not integrated into the main workflow loop).
- **`prompts/examine.py`** — Feynman/Socratic method prompts (defined but not yet used).

#### Streamlit UI (`ui/`)
- **`app.py`** — Main Streamlit application entry point. Orchestrates UI components and handles roadmap generation.
- **`components/preferences_form.py`** — User preferences input form (difficulty, goal, language).
- **`components/roadmap_visualizer.py`** — Interactive DAG visualization using streamlit-agraph.
- **`components/node_detail.py`** — Node detail view with progress tracking.
- **`utils/session_state.py`** — Streamlit session state management (pure session state, no database).

### Key patterns

- **LLM access** goes through OpenRouter (OpenAI-compatible API). Model and base URL are configured in `agents/roadmap.py` via `ChatOpenAI`.
- **Structured output** is enforced everywhere — agents return Pydantic models, not raw text.
- **Observability** via Langfuse (keys in `.env`, host configured as local instance).
- **Session-only persistence** — The UI uses Streamlit session state only; data is lost when the browser is closed. No database required.
- Roadmaps are DAGs (directed acyclic graphs) with `dependencies` on each node — the prompts and critic both enforce this constraint.

## Environment Variables

Required in `.env` (see `.env.example`):
- `OPENROUTER_API_KEY` — OpenRouter API key for LLM access
- `BASE_URL` — OpenRouter base URL (https://openrouter.ai/api/v1)
- `MODEL_NAME` — Primary model for roadmap generation
- `CRITIC_1_MODEL`, `CRITIC_2_MODEL`, `CRITIC_3_MODEL` — Models for multi-critic validation
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` — Optional observability
- `TAVILY_KEY` — Optional for future resource search feature

## Dependencies

Python 3.12+, managed with `uv`. Key libraries:

**Core**: `langgraph`, `langchain`, `langchain-openai`, `langfuse`, `tavily-python`, `pydantic`

**UI**: `streamlit`, `streamlit-agraph`, `pandas`

**RAG** (not yet integrated): `langchain-chroma`, `sentence-transformers`, `pymupdf4llm`

## UI Features

The Streamlit UI provides:
- 🎯 Interactive roadmap generation with user preferences
- 📊 DAG visualization with clickable nodes
- ✅ Learning progress tracking (not_started, in_progress, completed)
- ⚡ Session-only persistence (no database required)

**Note**: Data is stored only in browser session state and will be lost when the browser is closed. This simplified design eliminates the need for database setup.

See [UI_README.md](UI_README.md) for usage guide and [SETUP_GUIDE.md](SETUP_GUIDE.md) for installation.
