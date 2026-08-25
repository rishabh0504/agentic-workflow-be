import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel, AgentRunEventModel
from app.repositories.tool_repo import ToolRepository
from app.repositories.tool_operation_repo import ToolOperationRepository
from app.runtime.tool_runtime import ToolRuntime
from app.runtime.model_service import ModelService, ModelResponse


class AgentRuntime:
    """
    Authoritative backend Agent Runtime executing an autonomous multi-turn ReAct reasoning loop.
    Enforces maxTurns and timeout protection, parallelizes multiple tool calls per turn,
    logs chronological turn events, and persists the durable run state to PostgreSQL.
    """

    @staticmethod
    async def run(
        agent: AgentModel,
        prompt: str,
        db: AsyncSession,
        max_turns: Optional[int] = None,
        workflow_run_id: Optional[str] = None,
        timeout_s: float = 120.0,
        model_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        runtime_config = agent.runtime or {}
        limit_turns = max_turns or runtime_config.get("maxTurns", 8)
        limit_turns = min(max(1, limit_turns), 15)

        # 1. Initialize PostgreSQL Run Record
        agent_run = AgentRunModel(
            id=run_id,
            agent_id=agent.id,
            workflow_run_id=workflow_run_id,
            status="running",
            turns_executed=0,
            prompt=prompt,
            created_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        await db.commit()

        # 2. Resolve Attached Tools & Function Calling Declarations
        tool_repo = ToolRepository(db)
        op_repo = ToolOperationRepository(db)
        ollama_tools: List[Dict[str, Any]] = []
        tool_mapping: Dict[str, Any] = {}

        if agent.tool_ids:
            for tool_id in agent.tool_ids:
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
                    tool_mapping[fn_name] = target_bundle
                    tool_mapping[op_resp.name] = target_bundle
                    tool_mapping[tool_model.name] = target_bundle

                    schema_dict = op_resp.inputSchema
                    parameters = schema_dict if isinstance(schema_dict, dict) and schema_dict else {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query or input parameter"},
                            "url": {"type": "string", "description": "Target URL to fetch"},
                        },
                    }

                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "description": op_resp.description or f"{tool_model.displayName}: {op_resp.displayName}",
                            "parameters": parameters,
                        },
                    })

        # 3. Formulate System Prompt
        system_prompt = agent.instructions or "You are an expert autonomous AI Research Agent."
        if ollama_tools:
            system_prompt += (
                "\n\nOPERATIONAL PROTOCOL:"
                "\n1. You MUST use the provided tool(s) to search and fetch live data before forming conclusions."
                "\n2. When a tool is needed, trigger the structured tool call directly."
                "\n3. After receiving tool results, inspect the observations."
                "\n4. CRITICAL ANTI-HALLUCINATION CITATION RULE: You must ONLY cite exact, verbatim URLs returned in the tool observations. NEVER fabricate, invent, or guess URLs or path slugs."
                "\n5. Synthesize and write your complete, definitive response strictly adhering to the output schema."
            )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        turn_traces: List[Dict[str, Any]] = []
        all_tool_calls: List[Dict[str, Any]] = []
        model_config = {**(agent.model or {"providerId": "ollama", "model": "qwen3:8b"}), **(model_override or {})}

        # 4. Multi-Turn ReAct Loop
        try:
            for turn in range(1, limit_turns + 1):
                turn_start = time.perf_counter()

                # Model Chat Turn
                chat_res: ModelResponse = await ModelService.chat(
                    model_config=model_config,
                    messages=messages,
                    tools=ollama_tools if ollama_tools else None,
                    tool_mapping=tool_mapping,
                    timeout_s=timeout_s,
                )

                content = chat_res.content or ""
                proposed_tools = chat_res.tool_calls

                # CASE A: Final Output (No tool calls requested)
                if not proposed_tools:
                    final_text = content
                    if not final_text:
                        if turn > 1:
                            synth_res = await ModelService.chat(
                                model_config=model_config,
                                messages=messages,
                                tools=None,
                                timeout_s=timeout_s,
                            )
                            final_text = synth_res.content or ""
                        elif chat_res.thinking:
                            final_text = chat_res.thinking

                    turn_duration = round((time.perf_counter() - turn_start) * 1000, 2)
                    turn_trace = {
                        "turn": turn,
                        "type": "final_response",
                        "toolCallsProposed": [],
                        "durationMs": turn_duration,
                    }
                    turn_traces.append(turn_trace)

                    # Persist event
                    db.add(AgentRunEventModel(
                        agent_run_id=run_id,
                        turn=turn,
                        event_type="agent.completed",
                        payload=turn_trace,
                        created_at=datetime.now(timezone.utc),
                    ))

                    # Parse structured JSON if outputSchema is defined
                    structured_output = None
                    if agent.output_schema and isinstance(agent.output_schema, dict):
                        from app.runtime.contracts.validator import ContractValidator
                        from app.runtime.contracts.repair import SchemaRepairLoop

                        raw_candidate = final_text.strip()
                        if raw_candidate.startswith("```json"):
                            raw_candidate = raw_candidate.split("```json", 1)[1].split("```", 1)[0].strip()
                        elif raw_candidate.startswith("```"):
                            raw_candidate = raw_candidate.split("```", 1)[1].split("```", 1)[0].strip()

                        try:
                            parsed_json = json.loads(raw_candidate)
                            val_res = ContractValidator.validate(parsed_json, agent.output_schema, contract_name=agent.name)
                            if val_res.is_valid:
                                structured_output = parsed_json
                            else:
                                # Schema Repair Loop (Attempt 1)
                                repair_prompt = SchemaRepairLoop.build_repair_prompt(
                                    original_prompt=prompt,
                                    invalid_raw_output=parsed_json,
                                    expected_schema=agent.output_schema,
                                    validation_result=val_res,
                                    attempt=1,
                                )
                                repair_msg = list(messages) + [
                                    {"role": "assistant", "content": final_text},
                                    {"role": "user", "content": repair_prompt},
                                ]
                                repair_res = await ModelService.chat(
                                    model_config=model_config,
                                    messages=repair_msg,
                                    tools=None,
                                    timeout_s=timeout_s,
                                )
                                rep_cand = (repair_res.content or "").strip()
                                if rep_cand.startswith("```json"):
                                    rep_cand = rep_cand.split("```json", 1)[1].split("```", 1)[0].strip()
                                elif rep_cand.startswith("```"):
                                    rep_cand = rep_cand.split("```", 1)[1].split("```", 1)[0].strip()

                                repaired_json = json.loads(rep_cand)
                                rep_val = ContractValidator.validate(repaired_json, agent.output_schema, contract_name=agent.name)
                                if rep_val.is_valid:
                                    structured_output = repaired_json
                                    final_text = json.dumps(repaired_json, indent=2)
                        except Exception:
                            pass

                    # Finalize Run Record
                    total_duration = round((time.perf_counter() - start_time) * 1000, 2)
                    agent_run.status = "completed"
                    agent_run.turns_executed = turn
                    agent_run.final_output = {
                        "response": final_text or "Task completed.",
                        "structuredOutput": structured_output,
                        "toolCalls": all_tool_calls,
                        "turnTraces": turn_traces,
                        "turnsExecuted": turn,
                        "durationMs": total_duration,
                        "status": "SUCCESS",
                    }
                    agent_run.duration_ms = total_duration
                    agent_run.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    return agent_run.final_output

                # CASE B: Execute Tool Call(s) in Parallel
                tool_run_tasks = []
                for tc in proposed_tools:
                    target = tool_mapping.get(tc.name)
                    if target:
                        tool_run_tasks.append((
                            tc.name,
                            tc.arguments,
                            target,
                            ToolRuntime.execute_operation(
                                tool=target["tool"],
                                operation=target["operation"],
                                input_data=tc.arguments,
                            )
                        ))

                executed_observations = []
                if tool_run_tasks:
                    results = await asyncio.gather(*[t[3] for t in tool_run_tasks], return_exceptions=True)
                    for idx, res in enumerate(results):
                        fn_name, fn_args, target, _ = tool_run_tasks[idx]
                        if isinstance(res, Exception):
                            out_data = {"error": str(res)}
                            dur = 0.0
                        else:
                            out_data = res.output if res.status == "success" else {"error": res.error}
                            dur = res.durationMs

                        log_item = {
                            "tool": target["tool"].name,
                            "operation": target["operation"].name,
                            "arguments": fn_args,
                            "result": out_data,
                            "durationMs": dur,
                            "turn": turn,
                        }
                        all_tool_calls.append(log_item)
                        executed_observations.append((fn_name, fn_args, out_data, dur))

                turn_duration = round((time.perf_counter() - turn_start) * 1000, 2)
                turn_trace = {
                    "turn": turn,
                    "type": "tool_execution",
                    "toolCallsProposed": [
                        {"tool": o[0], "arguments": o[1], "durationMs": o[3]} for o in executed_observations
                    ],
                    "durationMs": turn_duration,
                }
                turn_traces.append(turn_trace)

                # Persist turn event
                db.add(AgentRunEventModel(
                    agent_run_id=run_id,
                    turn=turn,
                    event_type="turn.completed",
                    payload=turn_trace,
                    created_at=datetime.now(timezone.utc),
                ))
                await db.commit()

                # Native Conversation History: Assistant tool calls + Tool observation responses
                messages.append({
                    "role": "assistant",
                    "content": content if content else "",
                    "tool_calls": [
                        {
                            "id": f"call_{turn}_{i}",
                            "type": "function",
                            "function": {
                                "name": o[0],
                                "arguments": o[1],
                            }
                        }
                        for i, o in enumerate(executed_observations)
                    ]
                })

                for i, o in enumerate(executed_observations):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"call_{turn}_{i}",
                        "name": o[0],
                        "content": json.dumps(o[2]),
                    })

            # Exceeded maximum allowed turns
            total_duration = round((time.perf_counter() - start_time) * 1000, 2)
            agent_run.status = "limit_exceeded"
            agent_run.turns_executed = limit_turns
            agent_run.final_output = {
                "response": "Agent reached maximum execution turns limit.",
                "toolCalls": all_tool_calls,
                "turnTraces": turn_traces,
                "turnsExecuted": limit_turns,
                "durationMs": total_duration,
                "status": "LIMIT_EXCEEDED",
            }
            agent_run.duration_ms = total_duration
            agent_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return agent_run.final_output

        except Exception as e:
            total_duration = round((time.perf_counter() - start_time) * 1000, 2)
            agent_run.status = "failed"
            agent_run.error = str(e)
            agent_run.duration_ms = total_duration
            agent_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise RuntimeError(f"AgentRuntime failed at turn {agent_run.turns_executed + 1}: {str(e)}")
