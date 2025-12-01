"""
MCP Tools for ADK Agents
Wraps MCP server functions as callable tools for ADK agents.
These tools allow the LLM to reason about which tool to use.
"""
import requests
import json
from typing import Optional

# MCP Server URL
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
# These are simple wrappers that maintain the MCP interface

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
        # Validate JSON
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
