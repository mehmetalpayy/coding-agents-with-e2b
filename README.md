<h1 align="center"><strong>Coding Agents with E2B</strong></h1>

## Overview

Welcome to the **coding-agents-with-e2b** repository.

This project is a unified AI coding platform that combines three capabilities in a single Gradio interface:

- **Code Execution** — run arbitrary Python code in a secure cloud sandbox,
- **Data Analysis** — upload files and let the agent explore, analyse, and visualise your data,
- **Web Development** — build and preview full-stack Next.js apps with a live browser iframe.

All execution happens inside isolated [E2B](https://e2b.dev) cloud sandboxes. The agent is powered by the OpenAI Responses API (`gpt-4.1`) and routes each tool call to the correct sandbox automatically.

## Architecture

The platform runs two E2B sandboxes in parallel:

| Sandbox | Purpose | Tools |
|---|---|---|
| `code_sandbox` | Python execution, data analysis, uploaded files | `execute_code`, `execute_bash` |
| `web_sandbox` | Next.js 15 live app | `list_directory`, `read_file`, `write_file`, `replace_in_file`, `search_file_content`, `glob` |

A single agent loop handles all capabilities. The active UI tab determines which system prompt is used, keeping each mode focused and predictable.

## Repository Structure

```
coding-agents-with-e2b/
├── app/
│   ├── __init__.py
│   ├── agent.py            # Core agent loop with dual-sandbox support
│   ├── logger.py           # Rich-based structured logger
│   ├── prompts.py          # System prompts: SYSTEM_PROMPT_CODE_DATA, SYSTEM_PROMPT_WEB_DEV
│   ├── sandbox.py          # E2B sandbox lifecycle (create, setup, reconnect, clear)
│   ├── sbx_tools.py        # Filesystem tools uploaded into both sandboxes at startup
│   ├── tools.py            # Tool implementations + CODE_TOOLS / WEB_TOOLS routing
│   ├── tools_schemas.py    # OpenAI function-calling schemas (8 tools, unchanged)
│   └── ui.py               # Two-tab Gradio UI (Code & Data + Web Dev)
├── main.py                 # Entry point: boot sandboxes and launch UI
├── Makefile                # Shortcut: `make run`
├── pyproject.toml          # uv-managed dependencies
├── uv.lock
├── .env.example            # Required environment variable template
└── .gitignore
```

## UI

The Gradio interface has two tabs, each with its own conversation history and system prompt:

### 💻 Code & Data

- Chat with the agent to write and run Python code
- Upload any file (CSV, JSON, Excel, …) — it lands in the sandbox at `/home/user/<filename>`
- Matplotlib plots are displayed inline in the chat
- AIContext sidebar shows token usage

### 🌐 Web Dev

- Chat with the agent to build or modify a Next.js 15 app
- Live browser iframe shows the running app on port 3000
- Agent edits files directly in the sandbox; the dev server picks up changes automatically
- AIContext sidebar shows token usage

## Available Tools

| Tool | Sandbox | Description |
|---|---|---|
| `execute_code` | `code_sandbox` | Run Python code; captures stdout and PNG outputs |
| `execute_bash` | `code_sandbox` | Run shell commands (pip install, ls, etc.) |
| `list_directory` | `web_sandbox` | List files and subdirectories with pagination |
| `read_file` | `web_sandbox` | Read file content with optional offset and limit |
| `write_file` | `web_sandbox` | Create or overwrite a file |
| `replace_in_file` | `web_sandbox` | Replace specific text within a file |
| `search_file_content` | `web_sandbox` | Search across files with regex or fuzzy matching |
| `glob` | `web_sandbox` | Find files by glob pattern |

## Installation and Setup

### Prerequisites

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) package manager
- [OpenAI API key](https://platform.openai.com/api-keys)
- [E2B API key](https://e2b.dev/docs)

### 1. Clone the Repository

```bash
git clone https://github.com/mehmetalpayy/coding-agents-with-e2b.git
cd coding-agents-with-e2b
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
OPENAI_API_KEY=sk-...
E2B_API_KEY=e2b_...
```

### 3. Install Dependencies

```bash
uv sync
```

## Running

```bash
make run
```

This will:

1. Load environment variables from `.env`
2. Create (or reconnect to) two E2B sandboxes
3. Upload `sbx_tools.py` into both sandboxes and install `rapidfuzz`
4. Print the live Next.js URL
5. Launch the Gradio UI at `http://127.0.0.1:7860`

> **Sandbox caching:** sandbox IDs are saved in `code_sbx.cache` and `web_sbx.cache`. On restart, the app reconnects to the same running sandboxes instead of creating new ones, saving startup time.

## Troubleshooting

### Sandbox not starting

- Verify `E2B_API_KEY` is set correctly in `.env`.
- Delete `code_sbx.cache` and/or `web_sbx.cache` to force new sandbox creation.

### OpenAI errors

- Verify `OPENAI_API_KEY` is valid and has access to `gpt-4.1-mini`.

### File not found after upload

- Uploaded files go to `code_sandbox` at `/home/user/<filename>`.
- Use `execute_code` to verify: `import os; print(os.listdir('/home/user'))`.
- Do **not** use `list_directory` to look for uploaded files — it reads the web sandbox only.

### Next.js app not updating

- The dev server on port 3000 is always running. The agent must not restart it.
- If the iframe shows a stale page, hard-refresh the browser tab.

## Resources

This repository was built alongside the DeepLearning.AI **AI Agents in LangGraph** and **Building Coding Agents** courses:

- [E2B Documentation](https://e2b.dev/docs)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Gradio Documentation](https://www.gradio.app/docs)

## Contributing

1. Create a branch.
2. Make changes inside the relevant `app/` module.
3. Verify imports with `uv run python -c "from app.ui import ui; print('OK')"`.
4. Open a PR describing what changed and how it was tested.
