# AgentFlow BRE — Backend Service

Asynchronous Python FastAPI backend for the **AgentFlow Business Rule Engine (BRE)**. Built with **`uv`**, **SQLAlchemy 2.0 (Async)**, and **Supabase PostgreSQL**.

---

## Features

- **Dynamic Tools Registry (`/api/v1/tools`)**:
  - Full CRUD operations for `ToolDefinition` contracts.
  - Supports HTTP REST endpoints, SQL queries, JavaScript/Python functions, and Anthropic MCP tools.
  - JSON Schema Draft-07 input and output contracts.
  - Operational governance (`read`, `write`, `delete`), approval requirements, and timeout constraints.

- **Dynamic Agents Registry (`/api/v1/agents`)**:
  - Full CRUD operations for `AgentDefinition` contracts.
  - Flexible model provider configurations (OpenAI, Anthropic Claude, Google Gemini, DeepSeek, Ollama, vLLM, Custom Gateways).
  - Tool ID bindings from the catalog.
  - Max reasoning turns and execution timeout controls.
  - Structured output schemas.

- **Storage & Database**:
  - Direct integration with local **Supabase PostgreSQL** via `asyncpg`.
  - JSONB columns for flexible and deeply nested schema definitions.
  - Automatic table creation on server startup.

---

## Tech Stack

- **Python**: 3.12+
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv)
- **Framework**: FastAPI + Starlette + Uvicorn
- **ORM & Database**: SQLAlchemy 2.0 (async), `asyncpg`, `greenlet`, PostgreSQL (Supabase)
- **Validation**: Pydantic v2 & `pydantic-settings`
- **Testing**: `pytest`, `pytest-asyncio`, `httpx`

---

## Getting Started

### 1. Prerequisites
- Install **uv**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- Start your local Supabase instance:
  ```bash
  supabase start
  ```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
APP_NAME="AgentFlow Business Rule Engine (BRE) Backend"
APP_ENV="development"
APP_PORT=8000
APP_HOST="0.0.0.0"

# Local Supabase PostgreSQL Database
DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

# Supabase Local Service Keys & URLs
SUPABASE_URL="http://127.0.0.1:54321"
SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key_here"
SUPABASE_ANON_KEY="your_supabase_anon_key_here"
```

### 3. Run the Development Server
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## Running Tests

Execute the automated test suite with `pytest`:
```bash
PYTHONPATH=. uv run pytest
```

---

## API Reference

### Tools Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/tools` | List tools (supports `search`, `type`, `status` filters) |
| `POST` | `/api/v1/tools` | Register a new `ToolDefinition` |
| `GET` | `/api/v1/tools/{id}` | Get tool details by ID |
| `PUT` | `/api/v1/tools/{id}` | Update tool definition |
| `DELETE` | `/api/v1/tools/{id}` | Delete tool definition |

### Agents Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/agents` | List agents (supports `search`, `provider`, `status` filters) |
| `POST` | `/api/v1/agents` | Create a new `AgentDefinition` |
| `GET` | `/api/v1/agents/{id}` | Get agent details by ID |
| `PUT` | `/api/v1/agents/{id}` | Update agent definition |
| `DELETE` | `/api/v1/agents/{id}` | Delete agent definition |

---

## Project Structure

```
agentic-workflow-be/
├── .env                       # Environment configuration
├── pyproject.toml             # uv dependencies & project metadata
├── uv.lock                    # Dependency lockfile
├── pytest.ini                 # Pytest configuration
├── tests/
│   └── test_api.py            # API test suite
└── app/
    ├── main.py                # FastAPI app initialization, CORS & lifespans
    ├── config.py              # Settings loader (Pydantic BaseSettings)
    ├── database.py            # Async SQLAlchemy engine & session factory
    ├── models/                # SQLAlchemy models (PostgreSQL JSONB)
    │   ├── tool.py            # ToolModel
    │   └── agent.py           # AgentModel
    ├── schemas/               # Pydantic v2 schemas (ToolDefinition & AgentDefinition)
    │   ├── tool.py
    │   └── agent.py
    ├── repositories/          # Async database repository layer
    │   ├── tool_repo.py
    │   └── agent_repo.py
    └── routers/               # API route handlers
        ├── tools.py
        └── agents.py
```
