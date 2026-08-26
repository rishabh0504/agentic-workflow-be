import json
import re
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.repositories.tool_repo import ToolRepository
from app.repositories.tool_operation_repo import ToolOperationRepository
from app.runtime.tool_runtime import ToolRuntime

router = APIRouter(prefix="/providers", tags=["Providers & LLM Infrastructure"])


class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    system: Optional[str] = None
    stream: bool = False
    options: Optional[Dict[str, Any]] = None
    toolIds: Optional[List[str]] = None


@router.get("/ollama/models", summary="List installed local Ollama models")
async def list_ollama_models() -> List[Dict[str, Any]]:
    """
    Fetches the live list of models installed in the local Ollama instance (via `ollama list` / `/api/tags`).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                result = []
                for m in models:
                    result.append({
                        "name": m.get("name"),
                        "model": m.get("model"),
                        "size": m.get("size"),
                        "digest": m.get("digest"),
                        "details": m.get("details", {}),
                        "capabilities": m.get("capabilities", []),
                    })
                return result
            else:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Ollama returned error: {resp.text}",
                )
    except httpx.ConnectError:
        return [
            {"name": "qwen3:8b", "model": "qwen3:8b", "details": {"parameter_size": "8.2B"}},
            {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b", "details": {"parameter_size": "7.6B"}},
            {"name": "gemma3:4b", "model": "gemma3:4b", "details": {"parameter_size": "4.3B"}},
            {"name": "gpt-oss:20b-cloud", "model": "gpt-oss:20b-cloud", "details": {"parameter_size": "20.9B"}},
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query Ollama models: {str(e)}",
        )


@router.post("/ollama/generate", summary="Autonomous Agent reasoning with Tool Calling loop")
async def generate_ollama(
    payload: OllamaGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes reasoning with Ollama. If toolIds are provided, formats Ollama function declarations,
    inspects tool_calls (both native function calling & JSON output format), executes tools autonomously via ToolRuntime,
    and returns final synthesized response.
    """
    tool_repo = ToolRepository(db)
    op_repo = ToolOperationRepository(db)

    ollama_tools = []
    tool_mapping: Dict[str, Any] = {}

    if payload.toolIds:
        for tool_id in payload.toolIds:
            tool_model = await tool_repo.get_model_by_id(tool_id)
            if not tool_model or tool_model.status != "active":
                continue

            ops = await op_repo.get_by_tool_id(tool_id)
            for op_resp in ops:
                if not op_resp.enabled:
                    continue

                op_model = await op_repo.get_model_by_id(tool_id, op_resp.id)
                if not op_model:
                    continue

                fn_name = f"{tool_model.name}__{op_resp.name}"
                target_bundle = {
                    "tool": tool_model,
                    "operation": op_model,
                }
                # Map both qualified fn_name and short names
                tool_mapping[fn_name] = target_bundle
                tool_mapping[op_resp.name] = target_bundle
                tool_mapping[tool_model.name] = target_bundle

                schema_dict = op_resp.inputSchema
                parameters = schema_dict if isinstance(schema_dict, dict) and schema_dict else {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or parameters to execute",
                        },
                        "topK": {
                            "type": "number",
                            "description": "Number of results to retrieve",
                        },
                    },
                    "required": ["query"],
                }

                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": op_resp.description or f"{tool_model.displayName}: {op_resp.displayName}",
                        "parameters": parameters,
                    },
                })

    system_prompt = payload.system or "You are an autonomous AI Agent."
    if ollama_tools:
        system_prompt += "\nWhen you need live, external, or up-to-date information, call the available tools. After tool execution, synthesize a clear, helpful final response in natural language."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": payload.prompt},
    ]

    tool_call_logs = []

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            body: Dict[str, Any] = {
                "model": payload.model,
                "messages": messages,
                "stream": False,
            }
            if ollama_tools:
                body["tools"] = ollama_tools

            resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=body)
            if resp.status_code != 200:
                gen_body = {
                    "model": payload.model,
                    "prompt": payload.prompt,
                    "system": system_prompt,
                    "stream": False,
                }
                gen_resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=gen_body)
                if gen_resp.status_code == 200:
                    return gen_resp.json()
                raise HTTPException(status_code=resp.status_code, detail=f"Ollama error: {resp.text}")

            chat_data = resp.json()
            message = chat_data.get("message", {})
            raw_tool_calls = message.get("tool_calls", [])
            content_text = message.get("content", "").strip()

            # Handle models emitting raw JSON tool calls in text
            if not raw_tool_calls and (content_text.startswith("{") or "```json" in content_text):
                try:
                    json_str = content_text
                    if "```json" in content_text:
                        match = re.search(r"```json\s*(.*?)\s*```", content_text, re.DOTALL)
                        if match:
                            json_str = match.group(1)
                    parsed_json = json.loads(json_str)
                    target_name = parsed_json.get("name") or parsed_json.get("function")
                    if target_name and target_name in tool_mapping:
                        raw_tool_calls = [{
                            "function": {
                                "name": target_name,
                                "arguments": parsed_json.get("arguments", parsed_json.get("parameters", {})),
                            }
                        }]
                except Exception:
                    pass

            # If tool calls were triggered
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", {})

                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {"query": fn_args}

                    if fn_name in tool_mapping:
                        target = tool_mapping[fn_name]
                        run_res = await ToolRuntime.execute_operation(
                            tool=target["tool"],
                            operation=target["operation"],
                            input_data=fn_args,
                        )

                        tool_call_logs.append({
                            "tool": target["tool"].name,
                            "operation": target["operation"].name,
                            "arguments": fn_args,
                            "result": run_res.output or run_res.error,
                            "durationMs": run_res.durationMs,
                        })

                        # Append assistant action and tool observation
                        messages.append({
                            "role": "assistant",
                            "content": f"Calling tool {fn_name} with arguments {json.dumps(fn_args)}",
                        })
                        messages.append({
                            "role": "user",
                            "content": f"[Tool Output for {fn_name}]:\n{json.dumps(run_res.output, indent=2)}\n\nPlease provide the final answer to the original question using the tool search results above.",
                        })

                # Second turn: Synthesize final answer using live tool results
                synth_body = {
                    "model": payload.model,
                    "messages": messages,
                    "stream": False,
                }
                synth_resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=synth_body)
                if synth_resp.status_code == 200:
                    synth_data = synth_resp.json()
                    final_msg = synth_data.get("message", {}).get("content", "")
                    return {
                        "response": final_msg,
                        "toolCalls": tool_call_logs,
                        "eval_count": synth_data.get("eval_count", 0),
                        "total_duration": synth_data.get("total_duration", 0),
                        "status": "SUCCESS",
                    }

            # If no tool calls were needed
            return {
                "response": content_text,
                "toolCalls": [],
                "eval_count": chat_data.get("eval_count", 0),
                "total_duration": chat_data.get("total_duration", 0),
                "status": "SUCCESS",
            }

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Local Ollama instance is not running on port 11434.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama tool reasoning failed: {str(e)}")
