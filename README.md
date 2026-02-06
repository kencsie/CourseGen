# 🎓 CourseGen - AI Learning Roadmap Generator

An AI-powered learning path generation system with interactive visualization and progress tracking.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30+-FF4B4B.svg)](https://streamlit.io)

## 🌟 Features

- 🤖 **Multi-Model AI Generation** - Uses Claude, GPT-4, and Gemini for robust roadmap validation
- 📊 **Interactive DAG Visualization** - Explore learning paths as directed acyclic graphs
- 📚 **Example Roadmaps** - Browse pre-generated examples to explore system capabilities
- ✅ **Progress Tracking** - Mark nodes as not started, in progress, or completed
- ⚡ **No Database Required** - Simple session-based storage for quick setup
- 🌐 **Multilingual** - Support for Traditional Chinese and English
- 🎯 **Adaptive Difficulty** - Beginner, Intermediate, and Advanced levels
- 🔄 **Self-Correcting** - Generator-Critic loop ensures high-quality roadmaps

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.12+
- OpenRouter API key ([get one here](https://openrouter.ai))

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd CourseGen

# Install dependencies (using uv - recommended)
uv sync

# Or with pip
pip install -e .
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your credentials
nano .env
```

Minimum required configuration:
```env
OPENROUTER_API_KEY=your_key_here
BASE_URL=https://openrouter.ai/api/v1
```

### 4. Run the Application

```bash
# Using the convenience script
./scripts/run_ui.sh

# Or directly with Streamlit
streamlit run src/coursegen/ui/app.py
```

The app will open in your browser at `http://localhost:8501`

## 📖 Usage

### Browse Example Roadmaps

1. **Explore Examples**
   - Click the "📚 範例 Roadmaps" tab
   - Browse pre-generated learning path examples
   - Filter by difficulty, language, or tags

2. **View Example Details**
   - Click "查看範例" on any card
   - Explore the interactive roadmap visualization
   - Track progress (session-only)

3. **Generate Similar Roadmap**
   - Click "✨ 基於此範例生成新的" to create a customized version
   - Preferences will be pre-filled from the example
   - Modify and generate your own roadmap

### Generate a Learning Roadmap

1. **Enter Your Learning Topic**
   - Click the "🚀 生成 Roadmap" tab
   - Open the sidebar
   - Enter what you want to learn (e.g., "How to learn React.js?")

2. **Configure Preferences**
   - Select difficulty level (Beginner/Intermediate/Advanced)
   - Choose learning goal (Quick Start/Deep Dive)
   - Pick language (繁體中文/English)

3. **Generate**
   - Click "🚀 生成 Roadmap"
   - Wait 30-60 seconds for AI generation
   - See the interactive roadmap appear

### Track Your Progress

1. **Explore the Roadmap**
   - View the DAG visualization
   - Click any node to see details
   - Nodes are color-coded by status:
     - 🟢 Green = Not started
     - 🟡 Yellow = In progress
     - 🔵 Blue = Completed

2. **Update Progress**
   - Click "▶️ 標記為進行中" to start learning
   - Click "✅ 標記為已完成" when finished

### Session Persistence

⚠️ **Important**: Roadmaps and progress are stored in browser session state only. Data will be lost when you close the browser. This simplified design eliminates the need for database setup.

## 📚 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed installation and configuration guide
- **[UI_README.md](UI_README.md)** - Complete UI usage documentation
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical implementation details
- **[CLAUDE.md](CLAUDE.md)** - Project architecture and development guide

## 🏗️ Architecture

CourseGen uses a **Generator-Critic Loop** powered by LangGraph:

```
User Input → Roadmap Generator → Multi-Critic Validation
                ↑                         ↓
                └─────── Feedback ────────┘
                         (loops until valid)
                                ↓
                         Streamlit UI
                                ↓
                    Session State Storage
```

### Tech Stack

**Backend:**
- LangGraph - Agent orchestration
- LangChain - LLM framework
- OpenRouter - Multi-model LLM access
- Pydantic - Data validation

**Frontend:**
- Streamlit - Web framework
- streamlit-agraph - Graph visualization
- Session State - In-memory storage

## 🧪 Verification

Test the imports to verify your setup:

```bash
uv run python -c "import sys; sys.path.insert(0, 'src'); from coursegen.ui import app; print('✅ Setup successful')"
```

## 🛠️ Development

### Run CLI Workflow (without UI)

```bash
python -m src.coursegen.workflows.basic
```

### Run Jupyter Notebooks

```bash
uv run jupyter lab
# Notebooks are in notebook/ directory
```

### Project Structure

```
CourseGen/
├── src/coursegen/
│   ├── agents/          # LangGraph agent nodes
│   ├── prompts/         # System prompts
│   ├── workflows/       # LangGraph workflows
│   ├── schemas.py       # Pydantic models
│   └── ui/              # Streamlit UI
│       ├── app.py       # Main application
│       ├── components/  # UI components
│       └── utils/       # Utilities (session state, example loader)
├── examples/            # Pre-generated example roadmaps
│   └── roadmaps/        # Example JSON files and metadata
├── scripts/             # Setup and utility scripts
├── notebook/            # Jupyter notebooks
└── docs/                # Documentation
```

## 🐛 Troubleshooting

### Module Not Found

```bash
# Reinstall dependencies
uv sync

# Or clear and reinstall
rm -rf .venv
uv sync
```

### Roadmap Generation Fails

1. Check API key is valid in `.env`
2. Verify network connection
3. Try a different model (edit `MODEL_NAME` in `.env`)
4. Check API credits at OpenRouter

For more solutions, see [SETUP_GUIDE.md](SETUP_GUIDE.md#troubleshooting)

## 🗺️ Roadmap

### ✅ Phase 1 (Completed)
- [x] Multi-critic roadmap generation
- [x] Interactive Streamlit UI
- [x] DAG visualization
- [x] Progress tracking
- [x] Session-based storage (no database required)
- [x] Example roadmap browser with filtering

### 📋 Phase 2 (Planned)
- [ ] Interactive learning content
  - [ ] Feynman learning checks
  - [ ] Socratic dialogue mode
- [ ] External resource recommendations
  - [ ] Tavily search integration
  - [ ] Resource quality filtering
- [ ] Advanced analytics
  - [ ] Learning time tracking
  - [ ] Progress trends
  - [ ] Knowledge graph

### 🔮 Future Ideas
- [ ] User authentication
- [ ] Collaborative roadmaps
- [ ] Export to PDF/Image
- [ ] Mobile app
- [ ] Spaced repetition system
- [ ] AI tutor chatbot

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [Streamlit](https://streamlit.io) - Web framework
- [OpenRouter](https://openrouter.ai) - Multi-model LLM access
- [streamlit-agraph](https://github.com/ChrisDelClea/streamlit-agraph) - Graph visualization

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: your-email@example.com

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Made with ❤️ by the CourseGen Team**

Start your AI-powered learning journey today! 🎓✨
