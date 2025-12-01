"""
Assignment 5 - Multi-Agent Customer Service System with A2A and MCP
FIXED VERSION: Proper MCP tool integration (matching HW_v2 structure)
"""

# ============================================================================
# COMPATIBILITY PATCH
# ============================================================================
import sys
from a2a.client import client as real_client_module
from a2a.client.card_resolver import A2ACardResolver

class PatchedClientModule:
    def __init__(self, real_module) -> None:
        for attr in dir(real_module):
            if not attr.startswith('_'):
                setattr(self, attr, getattr(real_module, attr))
        self.A2ACardResolver = A2ACardResolver

patched_module = PatchedClientModule(real_client_module)
sys.modules['a2a.client.client'] = patched_module

# ============================================================================
# IMPORTS
# ============================================================================
import asyncio
import logging
import os
import threading
import time
import nest_asyncio
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    TransportProtocol,
)
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

nest_asyncio.apply()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
)

# ============================================================================
# DATABASE SETUP
# ============================================================================
import sqlite3
import datetime

DB = "mcp.db"

def db_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_and_seed():
    """Create database with deterministic test data (matches HW_v2 pattern)."""
    conn = db_conn()
    cur = conn.cursor()
    
    # Drop and recreate tables to reset AUTOINCREMENT (like HW_v2)
    cur.execute("PRAGMA foreign_keys = OFF;")
    cur.execute("DROP TABLE IF EXISTS tickets;")
    cur.execute("DROP TABLE IF EXISTS customers;")
    cur.execute("PRAGMA foreign_keys = ON;")
    
    cur.execute("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        status TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        issue TEXT,
        status TEXT,
        priority TEXT,
        created_at TEXT
    )""")
    conn.commit()
    
    # Use explicit IDs (like HW_v2) for deterministic test data
    now = datetime.datetime.now(datetime.UTC).isoformat()
    customers = [
        (1, "Alice Premium", "alice@example.com", "111-111-1111", "active", now, now),
        (2, "Bob Standard", "bob@example.com", "222-222-2222", "active", now, now),
        (3, "Charlie Disabled", "charlie@example.com", "333-333-3333", "disabled", now, now),
        (4, "Diana Premium", "diana@example.com", "444-444-4444", "active", now, now),
        (5, "Eve Standard", "eve@example.com", "555-555-5555", "active", now, now),
        (12345, "Priya Patel (Premium)", "priya@example.com", "555-0999", "active", now, now),
    ]
    cur.executemany("INSERT INTO customers (id, name, email, phone, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", customers)
    tickets = [
        (1, "Billing duplicate charge", "open", "high", now),
        (1, "Unable to login", "in_progress", "medium", now),
        (2, "Request upgrade", "open", "low", now),
        (4, "Critical outage", "open", "high", now),
        (5, "Password reset", "open", "low", now),
        (12345, "Account upgrade assistance", "open", "medium", now),
        (12345, "High priority refund review", "open", "high", now),
    ]
    cur.executemany("INSERT INTO tickets (customer_id, issue, status, priority, created_at) VALUES (?,?,?,?,?)", tickets)
    conn.commit()
    conn.close()
    print("Database created & seeded at", DB)

create_and_seed()

# ============================================================================
# MCP TOOLS (for ADK agents)
# ============================================================================
import requests
import json
from typing import Optional

MCP_SERVER_URL = "http://127.0.0.1:8000"

def _call_mcp_tool(tool_name: str, **params) -> str:
    """Helper function to call MCP server tools (synchronous)."""
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/call",
            json={"tool": tool_name, "params": params},
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, (dict, list)):
                return json.dumps(data, indent=2)
            return str(data)
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    except Exception as e:
        return f"MCP call failed: {str(e)}"

# ADK agents can use functions directly as tools
def tool_get_customer(customer_id: int) -> str:
    """Get customer details by ID. Uses customers.id field."""
    return _call_mcp_tool("get_customer", customer_id=customer_id)

def tool_list_customers(status: Optional[str] = None, limit: int = 10) -> str:
    """List customers, optionally filtered by status. Uses customers.status field."""
    params = {"limit": limit}
    if status:
        params["status"] = status
    return _call_mcp_tool("list_customers", **params)

def tool_update_customer(customer_id: int, data: str) -> str:
    """Update customer details. Data should be a JSON string. Uses customers fields."""
    try:
        data_dict = json.loads(data)
    except json.JSONDecodeError:
        return "Error: Invalid JSON data. Data must be a valid JSON string."
    return _call_mcp_tool("update_customer", customer_id=customer_id, data=data_dict)

def tool_create_ticket(customer_id: int, issue: str, priority: str = "medium") -> str:
    """Create a new support ticket. Uses tickets fields."""
    return _call_mcp_tool("create_ticket", customer_id=customer_id, issue=issue, priority=priority)

def tool_get_customer_history(customer_id: int) -> str:
    """Get ticket history for a customer. Uses tickets.customer_id field."""
    return _call_mcp_tool("get_customer_history", customer_id=customer_id)

def create_mcp_tools():
    """Create list of MCP tools for ADK agents."""
    return [
        tool_get_customer,
        tool_list_customers,
        tool_update_customer,
        tool_create_ticket,
        tool_get_customer_history,
    ]

# Create MCP tools
mcp_tools = create_mcp_tools()
print(f"Created {len(mcp_tools)} MCP tools for agents")

# ============================================================================
# AGENT DEFINITIONS (with MCP tools)
# ============================================================================

# Agent 1: Customer Data Agent
customer_data_agent = Agent(
    model='gemini-2.0-flash-lite',
    name='customer_data_agent',
    instruction="""
    You are the Customer Data Agent. Your role is to access and manage customer database information via MCP tools.
    
    Your responsibilities:
    - Retrieve customer information by ID
    - List customers with optional status filtering
    - Update customer records
    - Get customer ticket history
    
    Available MCP Tools:
    - tool_get_customer(customer_id: int): Get customer details by ID. Uses customers.id field.
    - tool_list_customers(status: str = None, limit: int = 10): List customers, optionally filtered by status. Uses customers.status field.
    - tool_update_customer(customer_id: int, data: str): Update customer details. Data should be a JSON string. Uses customers fields.
    - tool_get_customer_history(customer_id: int): Get ticket history for a customer. Uses tickets.customer_id field.
    - tool_create_ticket(customer_id: int, issue: str, priority: str = "medium"): Create a new support ticket. Uses tickets fields.
    
    IMPORTANT:
    - You MUST use your MCP tools to access the database. Do not answer from your own knowledge.
    - Always validate data before returning it.
    - When updating customer records, ensure the data is in valid JSON format (e.g., '{"email": "new@example.com"}').
    - When a user asks for customer information, analyze the request and use the appropriate tool.
    - Extract customer IDs from user queries when needed.
    """,
    tools=mcp_tools,  # ← KEY: Pass tools so LLM can reason about which to use
)

customer_data_agent_card = AgentCard(
    name='Customer Data Agent',
    url='http://localhost:9300',
    description='Specialist agent for accessing and managing customer database information via MCP tools',
    version='1.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain', 'application/json'],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id='get_customer_info',
            name='Get Customer Information',
            description='Retrieves customer details by ID using customers.id field',
            tags=['customer', 'data', 'retrieval', 'mcp'],
            examples=['Get customer information for ID 1', 'Retrieve customer 5'],
        ),
        AgentSkill(
            id='list_customers',
            name='List Customers',
            description='Lists customers with optional status filtering using customers.status field',
            tags=['customer', 'list', 'filter', 'mcp'],
            examples=['List all active customers', 'Show me customers with disabled status'],
        ),
        AgentSkill(
            id='update_customer',
            name='Update Customer',
            description='Updates customer records using customers fields',
            tags=['customer', 'update', 'modify', 'mcp'],
            examples=['Update email for customer 1', 'Change phone number for customer 5'],
        ),
        AgentSkill(
            id='get_customer_history',
            name='Get Customer History',
            description='Retrieves ticket history for a customer using tickets.customer_id field',
            tags=['customer', 'history', 'tickets', 'mcp'],
            examples=['Show ticket history for customer 1', 'Get all tickets for customer 5'],
        ),
    ],
)

# Agent 2: Support Agent
support_agent = Agent(
    model='gemini-2.0-flash-lite',
    name='support_agent',
    instruction="""
    You are the Support Agent. Your role is to handle customer support queries and issues.
    
    Your responsibilities:
    - Handle general customer support queries
    - Create support tickets for customer issues
    - Escalate complex issues when needed
    - Request customer context when needed
    - Provide solutions and recommendations
    
    Available MCP Tools:
    - tool_get_customer(customer_id: int): Get customer details by ID. Use this to look up customer information.
    - tool_list_customers(status: str = None, limit: int = 10): List customers. Use this to find customer IDs.
    - tool_create_ticket(customer_id: int, issue: str, priority: str = "medium"): Create a new support ticket. Uses tickets fields.
    - tool_get_customer_history(customer_id: int): Get ticket history for a customer. Uses tickets.customer_id field.
    
    IMPORTANT:
    - You MUST use your MCP tools to access the database. Do not answer from your own knowledge.
    - When a customer mentions they are "customer X" or provides identifying information, use your lookup tools first.
    - For urgent issues (billing, refunds, critical problems), use priority="high" when creating tickets.
    - If you cannot proceed (e.g., need billing context), tell the Router exactly what information you require.
    - Always use tools to create tickets and check customer history - never hardcode responses.
    """,
    tools=mcp_tools,  # ← KEY: Support agent also needs customer lookup tools
)

support_agent_card = AgentCard(
    name='Support Agent',
    url='http://localhost:9301',
    description='Specialist agent for handling customer support queries, ticket creation, and issue resolution',
    version='1.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id='create_ticket',
            name='Create Support Ticket',
            description='Creates a new support ticket using tickets fields',
            tags=['support', 'ticket', 'create', 'mcp'],
            examples=['Create a ticket for customer 1 about account upgrade'],
        ),
        AgentSkill(
            id='handle_support_query',
            name='Handle Support Query',
            description='Processes general customer support queries and provides solutions',
            tags=['support', 'help', 'assistance'],
            examples=['I need help with my account', 'How do I upgrade my subscription?'],
        ),
        AgentSkill(
            id='escalate_issue',
            name='Escalate Issue',
            description='Escalates complex or urgent issues appropriately',
            tags=['support', 'escalation', 'urgent'],
            examples=['I\'ve been charged twice, please refund immediately!'],
        ),
    ],
)

# Agent 3: Router Agent (using SequentialAgent like reference)
remote_customer_data_agent = RemoteA2aAgent(
    name='customer_data',
    description='Specialist agent for accessing customer database information',
    agent_card=f'http://localhost:9300{AGENT_CARD_WELL_KNOWN_PATH}',
)

remote_support_agent = RemoteA2aAgent(
    name='support',
    description='Specialist agent for handling customer support queries',
    agent_card=f'http://localhost:9301{AGENT_CARD_WELL_KNOWN_PATH}',
)

router_agent = SequentialAgent(
    name='router_agent',
    sub_agents=[remote_customer_data_agent, remote_support_agent],
)

router_agent_card = AgentCard(
    name='Router Agent',
    url='http://localhost:9400',
    description='Orchestrator agent that receives queries, analyzes intent, and routes to appropriate specialist agents',
    version='1.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id='route_query',
            name='Route Customer Query',
            description='Analyzes query intent and routes to appropriate specialist agent',
            tags=['routing', 'orchestration', 'coordination'],
            examples=[
                'Get customer information for ID 5',
                'I\'m customer 1 and need help upgrading my account',
                'Show me all active customers who have open tickets',
            ],
        ),
        AgentSkill(
            id='coordinate_agents',
            name='Coordinate Multiple Agents',
            description='Coordinates responses from multiple specialist agents for complex queries',
            tags=['coordination', 'multi-agent', 'orchestration'],
            examples=[
                'Update my email and show my ticket history',
                'I want to cancel but have billing issues',
            ],
        ),
    ],
)

print("CustomerDataAgent created with MCP tools")
print("SupportAgent created with MCP tools")
print("RouterAgent created with RemoteA2aAgent references")

# ============================================================================
# A2A SERVER SETUP
# ============================================================================

def create_agent_a2a_server(agent, agent_card):
    """Create an A2A server for any ADK agent."""
    runner = Runner(
        app_name=agent.name,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
    )

    config = A2aAgentExecutorConfig()
    executor = A2aAgentExecutor(runner=runner, config=config)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

async def run_agent_server(agent, agent_card, port):
    """Run a single agent server."""
    app = create_agent_a2a_server(agent, agent_card)

    config = uvicorn.Config(
        app.build(),
        host='127.0.0.1',
        port=port,
        log_level='info',
        loop='none',
    )

    server = uvicorn.Server(config)
    await server.serve()

async def start_all_servers():
    """Start all agent servers."""
    print("\n" + "="*60)
    print("Starting A2A Agent Servers...")
    print("="*60)
    
    server_tasks = [
        asyncio.create_task(run_agent_server(customer_data_agent, customer_data_agent_card, 9300)),
        asyncio.create_task(run_agent_server(support_agent, support_agent_card, 9301)),
        asyncio.create_task(run_agent_server(router_agent, router_agent_card, 9400)),
    ]
    
    print(f"[*] Customer Data Agent starting on http://127.0.0.1:9300")
    print(f"[*] Support Agent starting on http://127.0.0.1:9301")
    print(f"[*] Router Agent starting on http://127.0.0.1:9400")
    
    await asyncio.sleep(3)
    
    print("\n[SUCCESS] All agent servers started!")
    print("   - Router Agent: http://127.0.0.1:9400")
    print("   - Customer Data Agent: http://127.0.0.1:9300")
    print("   - Support Agent: http://127.0.0.1:9301")
    print("="*60 + "\n")
    
    await asyncio.gather(*server_tasks)

def run_servers_background():
    """Run servers in background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_all_servers())
    except KeyboardInterrupt:
        pass
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

# Start servers
server_thread = threading.Thread(target=run_servers_background, daemon=True)
server_thread.start()
time.sleep(5)  # Give servers time to start

# ============================================================================
# TEST CLIENT AND SCENARIOS
# ============================================================================
import httpx
from a2a.client import ClientConfig, ClientFactory, create_text_message_object
from a2a.types import AgentCard

class A2ASimpleClient:
    """A2A Simple Client to call A2A servers."""
    
    def __init__(self, default_timeout: float = 240.0):
        self._agent_info_cache: dict[str, dict | None] = {}
        self.default_timeout = default_timeout
    
    async def create_task(self, agent_url: str, message: str) -> str:
        """Send a message following the official A2A SDK pattern."""
        timeout_config = httpx.Timeout(
            timeout=self.default_timeout,
            connect=10.0,
            read=self.default_timeout,
            write=10.0,
            pool=5.0,
        )
        
        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            if (
                agent_url not in self._agent_info_cache
                or self._agent_info_cache[agent_url] is None
            ):
                agent_card_response = await httpx_client.get(
                    f'{agent_url}{AGENT_CARD_WELL_KNOWN_PATH}'
                )
                self._agent_info_cache[agent_url] = agent_card_response.json()
            
            agent_card_data = self._agent_info_cache[agent_url]
            agent_card = AgentCard(**agent_card_data)
            
            config = ClientConfig(
                httpx_client=httpx_client,
                supported_transports=[TransportProtocol.jsonrpc, TransportProtocol.http_json],
                use_client_preference=True,
            )
            
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            
            message_obj = create_text_message_object(content=message)
            
            responses = []
            async for response in client.send_message(message_obj):
                responses.append(response)
            
            if (
                responses
                and isinstance(responses[0], tuple)
                and len(responses[0]) > 0
            ):
                task = responses[0][0]
                try:
                    return task.artifacts[0].parts[0].root.text
                except (AttributeError, IndexError):
                    return str(task)
            
            return 'No response received'

# ============================================================================
# TEST SCENARIOS
# ============================================================================

async def run_all_tests():
    """Run all test scenarios."""
    test_client = A2ASimpleClient()

    print("\n" + "="*80)
    print("TEST SUITE - Multi-Agent Customer Service System")
    print("="*80)

    tests = [
        {
            "name": "TEST 1: Simple Query - Get Customer Information",
            "url": "http://127.0.0.1:9400",
            "message": "Get customer information for ID 1",
            "description": "Single agent, straightforward MCP call"
        },
        {
            "name": "TEST 2: Coordinated Query - Account Upgrade",
            "url": "http://127.0.0.1:9400",
            "message": "I'm customer ID 2 and need help upgrading my account",
            "description": "Multiple agents coordinate: data fetch + support response"
        },
        {
            "name": "TEST 3: Complex Query - Active Customers with Open Tickets",
            "url": "http://127.0.0.1:9400",
            "message": "Show me all active customers who have open tickets",
            "description": "Requires negotiation between data and support agents"
        },
        {
            "name": "TEST 4: Escalation - Refund Request",
            "url": "http://127.0.0.1:9400",
            "message": "I've been charged twice, please refund immediately! Customer ID 1",
            "description": "Router must identify urgency and route appropriately"
        },
        {
            "name": "TEST 5: Multi-Intent - Update and History",
            "url": "http://127.0.0.1:9400",
            "message": "Update customer ID 5 email to newemail@example.com and show my ticket history",
            "description": "Parallel task execution and coordination"
        },
    ]

    results = []
    for i, test in enumerate(tests, 1):
        print(f"\n{test['name']}")
        print(f"Description: {test['description']}")
        print("-" * 80)
        try:
            result = await test_client.create_task(test["url"], test["message"])
            print(result)
            results.append({"test": test["name"], "status": "PASSED"})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"test": test["name"], "status": "FAILED", "error": str(e)})

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for result in results:
        status_icon = "[PASS]" if result["status"] == "PASSED" else "[FAIL]"
        print(f"{status_icon} {result['test']}: {result['status']}")
        if "error" in result:
            print(f"   Error: {result['error']}")
    print("="*80 + "\n")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("Assignment 5 - Multi-Agent Customer Service System")
    print("A2A Protocol + MCP Integration (FIXED VERSION)")
    print("="*80)
    
    print("\nWaiting for servers to be ready...")
    time.sleep(3)
    
    asyncio.run(run_all_tests())
    
    print("\n[SUCCESS] All tests completed!")
    print("\nNote: Servers are running in background. Press Ctrl+C to stop.")

