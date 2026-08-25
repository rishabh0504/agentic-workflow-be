import time
import asyncio
from datetime import datetime, timezone
import secrets
from typing import Any, Dict, Optional
from app.models.tool import ToolModel
from app.models.tool_operation import ToolOperationModel
from app.schemas.tool import ToolRunResult, ToolRunStatus
from app.runtime.validator import validate_json_schema
from app.runtime.executor_registry import executor_registry


class ToolRuntime:
    @staticmethod
    async def execute_operation(
        tool: ToolModel,
        operation: ToolOperationModel,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolRunResult:
        run_id = f"run_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        executed_at = datetime.now(timezone.utc).isoformat()
        start_time = time.perf_counter()
        eval_context = context or {}

        # 1. State Validation
        if tool.status != "active":
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="execution_error",
                input=input_data,
                error=f"Parent Tool '{tool.name}' is {tool.status}, must be active to execute.",
                inputValid=True,
                outputValid=None,
                durationMs=0.0,
                executedAt=executed_at,
            )

        if not operation.enabled:
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="execution_error",
                input=input_data,
                error=f"Operation '{operation.name}' is currently disabled.",
                inputValid=True,
                outputValid=None,
                durationMs=0.0,
                executedAt=executed_at,
            )

        # 2. Input JSON Schema Validation
        is_input_valid, input_err = validate_json_schema(input_data, operation.input_schema)
        if not is_input_valid:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="input_validation_error",
                input=input_data,
                error=input_err,
                inputValid=False,
                outputValid=None,
                durationMs=duration_ms,
                executedAt=executed_at,
            )

        # 3. Resolve Implementation & Executor
        eval_context["operation"] = {"name": operation.name, "displayName": operation.display_name}
        impl = operation.implementation or {}
        impl_type = impl.get("type", tool.kind)
        try:
            executor = executor_registry.get(impl_type)
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="execution_error",
                input=input_data,
                error=str(e),
                inputValid=True,
                outputValid=None,
                durationMs=duration_ms,
                executedAt=executed_at,
            )

        # 4. Authoritative Timeout Protection
        timeout_ms = (operation.runtime or {}).get("timeoutMs", 30000)
        timeout_seconds = max(0.1, timeout_ms / 1000.0)

        try:
            async with asyncio.timeout(timeout_seconds):
                raw_output = await executor.execute(impl, input_data, eval_context)
        except asyncio.TimeoutError:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="timeout",
                input=input_data,
                error=f"Operation execution timed out after {timeout_ms}ms.",
                inputValid=True,
                outputValid=None,
                durationMs=duration_ms,
                executedAt=executed_at,
            )
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolRunResult(
                id=run_id,
                toolId=tool.id,
                operationId=operation.id,
                status="execution_error",
                input=input_data,
                error=f"Execution error: {str(e)}",
                inputValid=True,
                outputValid=None,
                durationMs=duration_ms,
                executedAt=executed_at,
            )

        # 5. Output JSON Schema Validation (if configured)
        output_schema = operation.output_schema
        output_valid = True
        if output_schema:
            is_output_valid, output_err = validate_json_schema(raw_output, output_schema)
            if not is_output_valid:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return ToolRunResult(
                    id=run_id,
                    toolId=tool.id,
                    operationId=operation.id,
                    status="output_validation_error",
                    input=input_data,
                    output=raw_output,
                    error=output_err,
                    inputValid=True,
                    outputValid=False,
                    durationMs=duration_ms,
                    executedAt=executed_at,
                )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ToolRunResult(
            id=run_id,
            toolId=tool.id,
            operationId=operation.id,
            status="success",
            input=input_data,
            output=raw_output,
            error=None,
            inputValid=True,
            outputValid=output_valid,
            durationMs=duration_ms,
            executedAt=executed_at,
        )
