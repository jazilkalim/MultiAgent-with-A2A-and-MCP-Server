"""
A2A Agents for Customer Service System
Each agent is independent with its own A2A interface
Agents use MCP tools - LLM reasons about which tool to use
"""
import os
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    TransportProtocol,
)
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from mcp_tools import create_mcp_tools

# MCP Tools
mcp_tools = create_mcp_tools()

# ============================================================================
# Agent 1: Customer Data Agent (Specialist)
# ============================================================================

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
    tools=mcp_tools,
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
            examples=[
                'Get customer information for ID 1',
                'Retrieve customer 5',
                'Show me customer details for ID 12345',
            ],
        ),
        AgentSkill(
            id='list_customers',
            name='List Customers',
            description='Lists customers with optional status filtering using customers.status field',
            tags=['customer', 'list', 'filter', 'mcp'],
            examples=[
                'List all active customers',
                'Show me customers with disabled status',
                'Get 10 customers',
            ],
        ),
        AgentSkill(
            id='update_customer',
            name='Update Customer',
            description='Updates customer records using customers fields',
            tags=['customer', 'update', 'modify', 'mcp'],
            examples=[
                'Update email for customer 1 to newemail@example.com',
                'Change phone number for customer 5',
            ],
        ),
        AgentSkill(
            id='get_customer_history',
            name='Get Customer History',
            description='Retrieves ticket history for a customer using tickets.customer_id field',
            tags=['customer', 'history', 'tickets', 'mcp'],
            examples=[
                'Show ticket history for customer 1',
                'Get all tickets for customer 5',
            ],
        ),
    ],
)

# ============================================================================
# Agent 2: Support Agent (Specialist)
# ============================================================================

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
    tools=mcp_tools,  # Support agent also needs customer lookup tools
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
            examples=[
                'Create a ticket for customer 1 about account upgrade',
                'Open a high priority ticket for billing issue',
            ],
        ),
        AgentSkill(
            id='handle_support_query',
            name='Handle Support Query',
            description='Processes general customer support queries and provides solutions',
            tags=['support', 'help', 'assistance'],
            examples=[
                'I need help with my account',
                'How do I upgrade my subscription?',
                'I have a billing question',
            ],
        ),
        AgentSkill(
            id='escalate_issue',
            name='Escalate Issue',
            description='Escalates complex or urgent issues appropriately',
            tags=['support', 'escalation', 'urgent'],
            examples=[
                'I\'ve been charged twice, please refund immediately!',
                'My account has been compromised',
            ],
        ),
    ],
)

# ============================================================================
# Agent 3: Router Agent (Orchestrator)
# ============================================================================

# Create remote references to other agents
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

# Router agent - uses SequentialAgent which automatically routes through sub-agents
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
        AgentSkill(
            id='analyze_intent',
            name='Analyze Query Intent',
            description='Analyzes customer queries to determine intent and required actions',
            tags=['analysis', 'intent', 'routing'],
            examples=[
                'Determine if query needs data retrieval or support',
                'Identify if multiple agents are needed',
            ],
        ),
    ],
)

# Export all agents and cards
__all__ = [
    'customer_data_agent',
    'customer_data_agent_card',
    'support_agent',
    'support_agent_card',
    'router_agent',
    'router_agent_card',
]
