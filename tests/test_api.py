import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.runtime.interpolator import interpolate_data

# Use NullPool for tests so asyncpg connections aren't shared across tasks
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
def test_interpolator_path_resolution():
    context = {
        "input": {"customerId": "cust_999", "details": {"name": "Alice"}},
        "integration": {"baseUrl": "https://api.internal.corp"},
    }

    url_template = "{{integration.baseUrl}}/customers/{{input.customerId}}"
    interpolated_url = interpolate_data(url_template, context)
    assert interpolated_url == "https://api.internal.corp/customers/cust_999"

    body_template = {"customerName": "{{input.details.name}}", "id": "{{input.customerId}}"}
    interpolated_body = interpolate_data(body_template, context)
    assert interpolated_body == {"customerName": "Alice", "id": "cust_999"}


@pytest.mark.asyncio
async def test_tool_container_and_operations_crud(client: AsyncClient):
    # 1. Create Tool Container
    tool_payload = {
        "name": "customer_api",
        "displayName": "Customer API Service",
        "description": "Enterprise customer management REST API",
        "category": "external",
        "kind": "http",
        "status": "active",
        "version": 1,
    }

    create_tool_res = await client.post("/api/v1/tools", json=tool_payload)
    assert create_tool_res.status_code == 201
    tool = create_tool_res.json()
    tool_id = tool["id"]
    assert tool["name"] == "customer_api"
    assert tool["kind"] == "http"

    # 2. Add Child Operation (get_customer)
    op_payload = {
        "name": "get_customer",
        "displayName": "Get Customer By ID",
        "description": "Fetch customer account details",
        "inputSchema": {
            "type": "object",
            "required": ["customerId"],
            "properties": {"customerId": {"type": "string"}},
        },
        "outputSchema": {
            "type": "object",
            "properties": {"statusCode": {"type": "integer"}},
        },
        "implementation": {
            "type": "http",
            "method": "GET",
            "url": "https://httpbin.org/get?customer_id={{input.customerId}}",
        },
        "classification": {"operation": "read", "requiresApproval": False},
        "runtime": {"timeoutMs": 15000},
        "enabled": True,
    }

    create_op_res = await client.post(f"/api/v1/tools/{tool_id}/operations", json=op_payload)
    assert create_op_res.status_code == 201
    op = create_op_res.json()
    op_id = op["id"]
    assert op["name"] == "get_customer"
    assert op["toolId"] == tool_id

    # 3. Add Second Operation (search_customers)
    op2_payload = {
        "name": "search_customers",
        "displayName": "Search Customers",
        "description": "Search customer directory",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "implementation": {
            "type": "http",
            "method": "POST",
            "url": "https://httpbin.org/post",
            "body": {"q": "{{input.query}}"},
        },
        "classification": {"operation": "read", "requiresApproval": False},
        "runtime": {"timeoutMs": 15000},
        "enabled": True,
    }
    create_op2_res = await client.post(f"/api/v1/tools/{tool_id}/operations", json=op2_payload)
    assert create_op2_res.status_code == 201

    # 4. List Operations for Tool
    list_ops_res = await client.get(f"/api/v1/tools/{tool_id}/operations")
    assert list_ops_res.status_code == 200
    assert len(list_ops_res.json()) == 2

    # 5. Fetch Full Tool Aggregate (eager operations)
    get_tool_res = await client.get(f"/api/v1/tools/{tool_id}")
    assert get_tool_res.status_code == 200
    assert len(get_tool_res.json()["operations"]) == 2

    # 6. Execute Operation Standalone (with valid input)
    exec_res = await client.post(
        f"/api/v1/tools/{tool_id}/operations/{op_id}/execute",
        json={"input": {"customerId": "12345"}},
    )
    assert exec_res.status_code == 200
    result = exec_res.json()
    assert result["status"] == "success"
    assert result["inputValid"] is True
    assert result["outputValid"] is True
    assert result["durationMs"] > 0

    # 7. Test Input Validation Failure
    exec_invalid_res = await client.post(
        f"/api/v1/tools/{tool_id}/operations/{op_id}/execute",
        json={"input": {}},  # Missing required customerId
    )
    assert exec_invalid_res.status_code == 200
    invalid_result = exec_invalid_res.json()
    assert invalid_result["status"] == "input_validation_error"
    assert invalid_result["inputValid"] is False
    assert invalid_result["outputValid"] is None

    # 8. Test Disabled Operation Rejection
    await client.patch(
        f"/api/v1/tools/{tool_id}/operations/{op_id}",
        json={"enabled": False},
    )
    exec_disabled_res = await client.post(
        f"/api/v1/tools/{tool_id}/operations/{op_id}/execute",
        json={"input": {"customerId": "12345"}},
    )
    assert exec_disabled_res.json()["status"] == "execution_error"
    assert "disabled" in exec_disabled_res.json()["error"]

    # 9. Delete Tool (Cascades Operations)
    del_res = await client.delete(f"/api/v1/tools/{tool_id}")
    assert del_res.status_code == 204
    check_tool_res = await client.get(f"/api/v1/tools/{tool_id}")
    assert check_tool_res.status_code == 404


@pytest.mark.asyncio
async def test_native_web_search_operation(client: AsyncClient):
    # Create Native Web Search Tool
    tool_payload = {
        "name": "web_search",
        "displayName": "Web Search Engine",
        "description": "Provider-agnostic live web search",
        "category": "native",
        "kind": "native",
        "status": "active",
        "version": 1,
    }
    create_tool_res = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = create_tool_res.json()["id"]

    # Add search_web operation
    op_payload = {
        "name": "search_web",
        "displayName": "Search Web",
        "description": "Live web search query",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "maxResults": {"type": "integer"}},
        },
        "outputSchema": {
            "type": "object",
            "required": ["results"],
            "properties": {"results": {"type": "array"}},
        },
        "implementation": {
            "type": "native",
            "handler": "web_search",
            "config": {"provider": "duckduckgo", "maxResults": 3},
        },
        "classification": {"operation": "read", "requiresApproval": False},
        "runtime": {"timeoutMs": 10000},
        "enabled": True,
    }
    create_op_res = await client.post(f"/api/v1/tools/{tool_id}/operations", json=op_payload)
    op_id = create_op_res.json()["id"]

    # Execute search_web standalone
    exec_res = await client.post(
        f"/api/v1/tools/{tool_id}/operations/{op_id}/execute",
        json={"input": {"query": "Artificial Intelligence", "maxResults": 2}},
    )
    assert exec_res.status_code == 200
    data = exec_res.json()
    assert data["status"] == "success"
    assert data["inputValid"] is True
    assert data["outputValid"] is True
    assert "results" in data["output"]
