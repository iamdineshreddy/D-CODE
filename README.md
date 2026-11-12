# D-ORCHESTRATOR

Local-first multi-provider AI engineering platform.

## Quick start (Windows)

1. Ensure Python 3.11+, Node 24, Ollama, OpenCode installed.
2. Install backend deps:
   ```
   cd backend
   pip install -r requirements.txt
   ```
3. (Optional) Build frontend:
   ```
   cd frontend
   npm install
   npm run build
   ```
4. Run:
   ```
   start.bat
   ```
   Or manually:
   ```
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   Dashboard: http://127.0.0.1:8000

## API keys

Set via environment variables:
OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY (or GEMINI_API_KEY),
OPENROUTER_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY,
FIREWORKS_API_KEY, XAI_API_KEY.

Ollama and OpenCode require no keys.

## Tests

```
cd backend
python -m pytest tests/ -q
```

## Notes

- Ollama models are auto-discovered.
- OpenCode models are discovered via `opencode models`.
- SQLite DB stored in backend/data/d_orchestrator.db.
- Checkpoints stored in backend/data/checkpoints.
