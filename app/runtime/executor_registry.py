from typing import Dict
from app.runtime.executors import (
    BaseExecutor,
    NativeExecutor,
    HttpExecutor,
    SqlExecutor,
    McpExecutor,
    CustomExecutor,
)


class ExecutorRegistry:
    def __init__(self):
        self._executors: Dict[str, BaseExecutor] = {
            "native": NativeExecutor(),
            "http": HttpExecutor(),
            "sql": SqlExecutor(),
            "mcp": McpExecutor(),
            "custom": CustomExecutor(),
        }

    def register(self, implementation_type: str, executor: BaseExecutor):
        self._executors[implementation_type.lower()] = executor

    def get(self, implementation_type: str) -> BaseExecutor:
        executor = self._executors.get(implementation_type.lower())
        if not executor:
            raise ValueError(f"No executor registered for implementation type '{implementation_type}'.")
        return executor


executor_registry = ExecutorRegistry()
