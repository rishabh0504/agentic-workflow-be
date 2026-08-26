from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx
import json
from app.config import settings


class ModelToolCall(BaseModel):
    id: Optional[str] = None
    name: str
    arguments: Dict[str, Any]


class ModelResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ModelToolCall] = Field(default_factory=list)
    thinking: Optional[str] = None  # Telemetry only
    eval_count: int = 0
    total_duration: int = 0


class ContentToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]


class ModelService:
    """
    Provider-agnostic LLM interface supporting normalized ModelResponse and ModelToolCall extraction.
    Strict 3-tier extraction hierarchy:
    1. Native provider tool_calls (Immediate winner, zero content inspection).
    2. Strict whole-object JSON validation via ContentToolCall (only raw JSON or single ```json block).
    3. Normal assistant content (No tool executed).
    Thinking stream is strictly telemetry and NEVER scanned or executed.
    """

    @staticmethod
    async def chat(
        model_config: Dict[str, Any],
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_mapping: Optional[Dict[str, Any]] = None,
        timeout_s: float = 90.0,
    ) -> ModelResponse:
        provider_id = (model_config.get("providerId") or "ollama").lower()
        model_name = model_config.get("model") or "qwen3:8b"

        return await ModelService._chat_ollama(
            model_name=model_name,
            messages=messages,
            tools=tools,
            tool_mapping=tool_mapping or {},
            timeout_s=timeout_s,
        )

    @staticmethod
    async def _chat_ollama(
        model_name: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        tool_mapping: Dict[str, Any],
        timeout_s: float = 90.0,
    ) -> ModelResponse:
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama chat error (status {resp.status_code}): {resp.text}")

            chat_data = resp.json()
            message = chat_data.get("message", {})
            raw_tool_calls = message.get("tool_calls", [])
            content_text = message.get("content", "") or ""
            thinking_text = message.get("thinking", "") or ""

            # -------------------------------------------------------------
            # TIER 1: Native Provider tool_calls (Immediate Winner)
            # -------------------------------------------------------------
            if raw_tool_calls:
                parsed_calls: List[ModelToolCall] = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {"query": fn_args}
                    if isinstance(fn_args, dict) and fn_name:
                        parsed_calls.append(ModelToolCall(
                            id=tc.get("id"),
                            name=fn_name,
                            arguments=fn_args,
                        ))

                if parsed_calls:
                    return ModelResponse(
                        content=content_text.strip() if content_text else None,
                        tool_calls=parsed_calls,
                        thinking=thinking_text.strip() if thinking_text else None,
                        eval_count=chat_data.get("eval_count", 0),
                        total_duration=chat_data.get("total_duration", 0),
                    )

            # -------------------------------------------------------------
            # TIER 2: Strict Whole-Object JSON Tool Call Validation
            # -------------------------------------------------------------
            trimmed_content = content_text.strip()
            if trimmed_content:
                json_candidate = None
                if trimmed_content.startswith("{") and trimmed_content.endswith("}"):
                    json_candidate = trimmed_content
                elif trimmed_content.startswith("```json") and trimmed_content.endswith("```"):
                    json_candidate = trimmed_content[7:-3].strip()
                elif trimmed_content.startswith("```") and trimmed_content.endswith("```"):
                    json_candidate = trimmed_content[3:-3].strip()

                if json_candidate and json_candidate.startswith("{") and json_candidate.endswith("}"):
                    try:
                        parsed_obj = json.loads(json_candidate)
                        if isinstance(parsed_obj, dict):
                            call = ContentToolCall.model_validate(parsed_obj)
                            # Must match a registered tool in tool_mapping
                            if call.name in tool_mapping or not tool_mapping:
                                return ModelResponse(
                                    content=None,
                                    tool_calls=[ModelToolCall(name=call.name, arguments=call.arguments)],
                                    thinking=thinking_text.strip() if thinking_text else None,
                                    eval_count=chat_data.get("eval_count", 0),
                                    total_duration=chat_data.get("total_duration", 0),
                                )
                    except Exception:
                        pass

            # -------------------------------------------------------------
            # TIER 3: Normal Assistant Content (No Tools Executed)
            # -------------------------------------------------------------
            return ModelResponse(
                content=trimmed_content if trimmed_content else None,
                tool_calls=[],
                thinking=thinking_text.strip() if thinking_text else None,
                eval_count=chat_data.get("eval_count", 0),
                total_duration=chat_data.get("total_duration", 0),
            )
