import asyncio
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models import (
    WorkflowModel,
    WorkflowVersionModel,
    WorkflowRunModel,
    WorkflowNodeRunModel,
    AgentModel,
    AgentRunModel,
    AgentRunEventModel,
    ToolModel,
    ToolOperationModel,
    GuardrailModel,
    GuardrailRuleModel,
    GuardrailBindingModel,
    GuardrailExecutionModel,
    IOContractModel,
)

from app.repositories.workflow_repo import WorkflowRepository
from app.repositories.agent_repo import AgentRepository
from app.repositories.tool_repo import ToolRepository
from app.repositories.io_contract_repo import IOContractRepository

from app.schemas.workflow import WorkflowCreate, WorkflowVersionCreate
from app.schemas.agent import AgentCreate, AgentModelConfig, AgentRuntimeConfig
from app.schemas.tool import ToolCreate, ToolOperationCreate, ToolRuntimeConfig
from app.schemas.io_contract import IOContractCreate


async def seed_production_contracts_and_workflows():
    print("🧹 Cleaning database completely to ensure pure single-workflow state...")
    async with AsyncSessionLocal() as db:
        await db.execute(delete(GuardrailExecutionModel))
        await db.execute(delete(GuardrailBindingModel))
        await db.execute(delete(GuardrailModel))
        await db.execute(delete(AgentRunEventModel))
        await db.execute(delete(AgentRunModel))
        await db.execute(delete(WorkflowRunModel))
        await db.execute(delete(WorkflowVersionModel))
        await db.execute(delete(WorkflowModel))
        await db.execute(delete(ToolOperationModel))
        await db.execute(delete(ToolModel))
        await db.execute(delete(AgentModel))
        await db.execute(delete(IOContractModel))
        await db.commit()

        contract_repo = IOContractRepository(db)
        tool_repo = ToolRepository(db)
        agent_repo = AgentRepository(db)
        workflow_repo = WorkflowRepository(db)

        print("\n🚀 Step 1: Seeding 3 Core IO Contracts...")
        # 1. Research Request Contract
        c_res_req = await contract_repo.create(IOContractCreate(
            name="research_request",
            version=1,
            displayName="Research Request Contract",
            description="Topic and query input payload for intelligence gathering",
            schema_={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Research search prompt or topic"}
                }
            }
        ))

        # 2. Research Result Contract
        c_res_res = await contract_repo.create(IOContractCreate(
            name="research_result",
            version=1,
            displayName="Research Result Intelligence Contract",
            description="Verified research intelligence with facts and sources",
            schema_={
                "type": "object",
                "required": ["market_summary", "verified_facts", "verified_sources"],
                "properties": {
                    "market_summary": {"type": "string"},
                    "verified_facts": {
                        "type": "array",
                        "items": {"type": "object", "properties": {"claim": {"type": "string"}, "metric": {"type": "string"}}}
                    },
                    "verified_sources": {
                        "type": "array",
                        "items": {"type": "object", "properties": {"url": {"type": "string"}, "title": {"type": "string"}}}
                    }
                }
            }
        ))

        # 3. Podcast Draft Contract
        c_pod_draft = await contract_repo.create(IOContractCreate(
            name="podcast_draft",
            version=1,
            displayName="Podcast Dialogue Script Contract",
            description="Broadcast Host & Guest conversation script citing verified sources",
            schema_={
                "type": "object",
                "required": ["episode_title", "duration_estimate", "script_dialogue"],
                "properties": {
                    "episode_title": {"type": "string"},
                    "duration_estimate": {"type": "string"},
                    "script_dialogue": {"type": "string"}
                }
            }
        ))

        print("✅ Step 1 Complete: 3 Clean Contracts Registered!")

        print("\n🚀 Step 2: Seeding DuckDuckGo Web Search Tool...")
        t_search = await tool_repo.create(ToolCreate(
            id="tool_web_search_01",
            name="web_search",
            displayName="DuckDuckGo Web Search & Live Intelligence Scraper",
            description="Fetches live verified web search results and news data from DuckDuckGo.",
            kind="native",
            category="native",
            operations=[
                ToolOperationCreate(
                    id="op_search_01",
                    toolId="tool_web_search_01",
                    name="web_search",
                    displayName="DuckDuckGo Search",
                    description="Performs live web search for verified facts and sources.",
                    # Critical: implementation must declare type=native + handler=web_search
                    # so tool_runtime.py routes to NativeExecutor → WebSearchService
                    implementation={
                        "type": "native",
                        "handler": "web_search",
                        "config": {"provider": "duckduckgo"},
                    },
                    inputSchema={
                        "type": "object",
                        "required": ["query"],
                        "properties": {
                            "query": {"type": "string", "description": "Search query string for DuckDuckGo"},
                            "topK": {"type": "integer", "default": 5, "description": "Max number of results"},
                        },
                    },
                    runtime=ToolRuntimeConfig(timeoutMs=120000),
                )
            ]
        ))

        print("✅ Step 2 Complete: 1 DuckDuckGo Tool Registered!")

        print("\n🚀 Step 3: Seeding 3 Generic Role-Based Autonomous Agents...")
        # 1. Intent Identifier Agent
        agent_intent = await agent_repo.create(AgentCreate(
            id="agent_intent_identifier",
            name="intent_identifier_agent",
            displayName="Intent Identifier & Query Formulator",
            description="Analyzes user inquiry, identifies research intent, and formulates targeted search keywords.",
            model=AgentModelConfig(providerId="ollama", model="gpt-oss:20b-cloud", temperature=0.1),
            runtime=AgentRuntimeConfig(maxTurns=3, timeoutMs=120000),
            instructions=(
                "You are an expert Intent Identifier and Search Query Formulator.\n"
                "Analyze the user's inquiry, extract the core research topic, and generate an optimal, concise web search query.\n"
                "Return a valid JSON object with the following fields: 'search_intent', 'target_topic', and 'optimized_search_query'."
            ),
            toolIds=[],
            inputSchema=c_res_req.schema_,
            outputSchema={
                "type": "object",
                "required": ["search_intent", "target_topic", "optimized_search_query"],
                "properties": {
                    "search_intent": {"type": "string"},
                    "target_topic": {"type": "string"},
                    "optimized_search_query": {"type": "string"}
                }
            },
        ))

        # 2. Research Investigator Agent (with DuckDuckGo Search)
        agent_research = await agent_repo.create(AgentCreate(
            id="agent_research_investigator",
            name="research_investigator",
            displayName="Autonomous Web Research Investigator",
            description="Performs live DuckDuckGo web searches and extracts verified facts and exact URLs.",
            model=AgentModelConfig(providerId="ollama", model="gpt-oss:20b-cloud", temperature=0.2),
            runtime=AgentRuntimeConfig(maxTurns=4, timeoutMs=120000),
            instructions=(
                "You are an autonomous Web Research Investigator.\n"
                "Execute the web_search tool exactly ONCE with the user's search query to gather real-time data from DuckDuckGo.\n"
                "CRITICAL CITATION RULE: You must ONLY cite exact URLs present in the tool observations. NEVER invent or fabricate URLs.\n"
                "After receiving tool results, immediately synthesize and return a structured JSON object matching the research_result schema containing 'market_summary', 'verified_facts', and 'verified_sources'."
            ),
            toolIds=[t_search.id],
            outputSchema=c_res_res.schema_,
        ))

        # 3. Generic Podcast Producer Agent (Host & Guest)
        agent_podcast = await agent_repo.create(AgentCreate(
            id="agent_podcast_producer",
            name="podcast_producer",
            displayName="Podcast Producer (Host & Guest)",
            description="Scripts compelling broadcast dialogues between Host and Guest Industry Expert citing verified research.",
            model=AgentModelConfig(providerId="ollama", model="gpt-oss:20b-cloud", temperature=0.3),
            runtime=AgentRuntimeConfig(maxTurns=3, timeoutMs=120000),
            instructions=(
                "You are a Professional Podcast Producer.\n"
                "Create an engaging, fast-paced podcast dialogue discussing the provided research topic.\n"
                "FORMAT RULES:\n"
                "1. Always use 'Host:' for the podcast host and 'Guest:' for the guest industry expert. Do NOT use arbitrary fictional names.\n"
                "2. Reference only facts and statistics provided in the research intelligence.\n"
                "3. At the end of the script, include a 'References:' section citing ONLY the exact URLs provided in the research data.\n"
                "Return a structured JSON object matching the podcast_draft schema with 'episode_title', 'duration_estimate', and 'script_dialogue'."
            ),
            toolIds=[],
            inputSchema=c_res_res.schema_,
            outputSchema=c_pod_draft.schema_,
        ))

        print("✅ Step 3 Complete: 3 Production Agents Registered (Generic Host/Guest & DuckDuckGo Search)!")

        print("\n🚀 Step 4: Seeding Single Clean Production Pipeline...")
        await workflow_repo.create(WorkflowCreate(
            id="wf_research_podcast_pipeline",
            name="research_and_podcast_production_pipeline",
            displayName="Autonomous Research & Podcast Production Pipeline",
            description="User Query -> Intent Identifier -> DuckDuckGo Research Agent (with Tool) -> Generic Host/Guest Podcast Producer -> Final Broadcast Output.",
            category="podcast",
            status="PUBLISHED",
            initialVersion=WorkflowVersionCreate(
                inputSchema=c_res_req.schema_,
                outputSchema=c_pod_draft.schema_,
                nodes=[
                    {
                        "id": "start-node",
                        "type": "start",
                        "position": {"x": 80, "y": 200},
                        "data": {
                            "label": "User Research Query",
                            "nodeType": "start",
                            "inputSchema": c_res_req.schema_,
                            "mockPayload": "{\"query\": \"Analyze 2025 Dubai luxury real estate yields and investment trends\"}",
                            "triggerType": "manual"
                        }
                    },
                    {
                        "id": "agent-intent",
                        "type": "agent",
                        "position": {"x": 400, "y": 200},
                        "data": {
                            "label": "Intent Identifier Agent",
                            "name": "intent_identifier_agent",
                            "agentId": "intent_identifier_agent",
                            "nodeType": "agent",
                            "tools": [],
                            "inputSchema": c_res_req.schema_,
                        }
                    },
                    {
                        "id": "agent-research",
                        "type": "agent",
                        "position": {"x": 750, "y": 200},
                        "data": {
                            "label": "DuckDuckGo Research Agent",
                            "name": "research_investigator",
                            "agentId": "research_investigator",
                            "nodeType": "agent",
                            "tools": [t_search.id],
                            "outputSchema": c_res_res.schema_
                        }
                    },
                    {
                        "id": "agent-producer",
                        "type": "agent",
                        "position": {"x": 1100, "y": 200},
                        "data": {
                            "label": "Host & Guest Podcast Producer",
                            "name": "podcast_producer",
                            "agentId": "podcast_producer",
                            "nodeType": "agent",
                            "tools": [],
                            "inputSchema": c_res_res.schema_,
                            "outputSchema": c_pod_draft.schema_
                        }
                    },
                    {
                        "id": "end-node",
                        "type": "end",
                        "position": {"x": 1450, "y": 200},
                        "data": {
                            "label": "Broadcast Podcast Output",
                            "nodeType": "end",
                            "outputMode": "DIRECT",
                            "outputSchema": c_pod_draft.schema_
                        }
                    }
                ],
                edges=[
                    {"id": "e1", "source": "start-node", "target": "agent-intent"},
                    {"id": "e2", "source": "agent-intent", "target": "agent-research"},
                    {"id": "e3", "source": "agent-research", "target": "agent-producer"},
                    {"id": "e4", "source": "agent-producer", "target": "end-node"},
                ]
            )
        ))

        print("✅ Step 4 Complete: 1 Generic Multi-Agent Production Workflow Seeded Successfully!")


if __name__ == "__main__":
    asyncio.run(seed_production_contracts_and_workflows())
