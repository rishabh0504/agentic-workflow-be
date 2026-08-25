from abc import ABC, abstractmethod
from typing import Any, Dict
from app.runtime.interpolator import interpolate_data
from app.runtime.native_handlers.web_search import WebSearchService
import httpx


class BaseExecutor(ABC):
    @abstractmethod
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        pass


from app.runtime.native_handlers.page_fetcher import PageFetcherService


class NativeExecutor(BaseExecutor):
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        handler = implementation.get("handler") or (context.get("operation") or {}).get("name", "")
        config = implementation.get("config", {}) or {}

        if handler == "web_search":
            query = input_data.get("query") if isinstance(input_data, dict) else str(input_data)
            max_results = input_data.get("topK", input_data.get("maxResults", config.get("maxResults", 5))) if isinstance(input_data, dict) else 5
            provider = config.get("provider", "duckduckgo")
            results = await WebSearchService.search(query=str(query or ""), max_results=int(max_results or 5), provider=provider)
            return {"results": results}

        if handler == "fetch_page" or handler == "page_fetcher":
            url = input_data.get("url") if isinstance(input_data, dict) else str(input_data)
            max_chars = input_data.get("maxChars", config.get("maxChars", 4000)) if isinstance(input_data, dict) else 4000
            result = await PageFetcherService.fetch(url=str(url or ""), max_chars=int(max_chars or 4000))
            return result

        raise ValueError(f"Unknown native handler '{handler}'.")


class HttpExecutor(BaseExecutor):
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        # Build evaluation context
        eval_context = {
            "input": input_data,
            "integration": context.get("integration", {}),
            "config": context.get("config", {}),
        }

        raw_url = implementation.get("url", "")
        method = implementation.get("method", "POST").upper()
        raw_headers = implementation.get("headers") or {}
        raw_query = implementation.get("query") or {}
        raw_body = implementation.get("body")

        # Interpolate variables safely
        url = interpolate_data(raw_url, eval_context)
        headers = interpolate_data(raw_headers, eval_context)
        params = interpolate_data(raw_query, eval_context)
        body = interpolate_data(raw_body, eval_context) if raw_body is not None else None

        async with httpx.AsyncClient(timeout=30.0) as client:
            req_kwargs: Dict[str, Any] = {"headers": headers, "params": params}
            if body is not None:
                if isinstance(body, (dict, list)):
                    req_kwargs["json"] = body
                else:
                    req_kwargs["content"] = str(body)

            response = await client.request(method, url, **req_kwargs)
            try:
                data = response.json()
            except Exception:
                data = response.text

            return {
                "statusCode": response.status_code,
                "data": data,
                "headers": dict(response.headers),
            }


class SqlExecutor(BaseExecutor):
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        # MVP Executor Abstraction Interface
        query = implementation.get("query", "")
        params = implementation.get("parameters", {})
        integration_id = implementation.get("integrationId", "")
        return {
            "mocked": True,
            "integrationId": integration_id,
            "executedQuery": query,
            "parameters": params,
            "rows": [],
        }


class McpExecutor(BaseExecutor):
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        # MVP Executor Abstraction Interface
        server_id = implementation.get("serverId", "")
        tool_name = implementation.get("toolName", "")
        return {
            "mocked": True,
            "serverId": server_id,
            "toolName": tool_name,
            "result": f"MCP execution for {tool_name} on server {server_id} prepared.",
        }


class CustomExecutor(BaseExecutor):
    async def execute(self, implementation: Dict[str, Any], input_data: Any, context: Dict[str, Any]) -> Any:
        handler = implementation.get("handler", "")
        return {
            "customHandler": handler,
            "status": "dispatched",
            "input": input_data,
        }
