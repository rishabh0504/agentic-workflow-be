-- ==============================================================================
-- Migration: 001_create_tools_operations_agents.sql
-- Description: Creates the Tools (Container), Tool Operations (1:N), and Agents tables
-- ==============================================================================

-- 1. Tools Container Table
CREATE TABLE IF NOT EXISTS public.tools (
    id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(128) UNIQUE NOT NULL,
    display_name VARCHAR(256) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category VARCHAR(32) NOT NULL DEFAULT 'external', -- 'native' | 'external'
    kind VARCHAR(32) NOT NULL,                        -- 'native' | 'http' | 'sql' | 'mcp' | 'custom'
    status VARCHAR(32) NOT NULL DEFAULT 'active',     -- 'draft' | 'active' | 'disabled'
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Tool Operations Child Table (1:N with Tools)
CREATE TABLE IF NOT EXISTS public.tool_operations (
    id VARCHAR(128) PRIMARY KEY,
    tool_id VARCHAR(128) NOT NULL REFERENCES public.tools(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    display_name VARCHAR(256) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    input_schema JSONB NOT NULL DEFAULT '{"type": "object", "properties": {}}'::jsonb,
    output_schema JSONB,
    implementation JSONB NOT NULL DEFAULT '{}'::jsonb,
    classification JSONB NOT NULL DEFAULT '{"operation": "read", "requiresApproval": false}'::jsonb,
    runtime JSONB NOT NULL DEFAULT '{"timeoutMs": 30000}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tool_operation_name UNIQUE (tool_id, name)
);

CREATE INDEX IF NOT EXISTS ix_tool_operations_tool_id ON public.tool_operations(tool_id);

-- 3. Agents Table
CREATE TABLE IF NOT EXISTS public.agents (
    id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(128) UNIQUE NOT NULL,
    display_name VARCHAR(256) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    model JSONB NOT NULL DEFAULT '{"providerId": "openai", "model": "gpt-4o", "temperature": 0.3}'::jsonb,
    instructions TEXT NOT NULL DEFAULT '',
    tool_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_schema JSONB,
    output_schema JSONB,
    runtime JSONB NOT NULL DEFAULT '{"maxTurns": 10, "timeoutMs": 60000}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tools_name ON public.tools(name);
CREATE INDEX IF NOT EXISTS ix_agents_name ON public.agents(name);
