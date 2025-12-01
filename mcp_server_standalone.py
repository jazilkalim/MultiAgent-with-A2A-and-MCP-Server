"""Standalone MCP Server for testing."""
import sqlite3
import datetime
import asyncio
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

# Database setup - Use mcp.db in current directory
DB = "mcp.db"

def db_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database if needed (matches notebook seeding)
def init_db():
    """Initialize database with deterministic test data (matches HW_v2 pattern)."""
    conn = db_conn()
    cur = conn.cursor()
    
    # Drop and recreate tables to reset AUTOINCREMENT (like HW_v2)
    cur.execute("PRAGMA foreign_keys = OFF;")
    cur.execute("DROP TABLE IF EXISTS tickets;")
    cur.execute("DROP TABLE IF EXISTS customers;")
    cur.execute("PRAGMA foreign_keys = ON;")
    
    # Create tables
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
    cur.executemany(
        "INSERT INTO customers (id, name, email, phone, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        customers
    )
    tickets = [
        (1, "Billing duplicate charge", "open", "high", now),
        (1, "Unable to login", "in_progress", "medium", now),
        (2, "Request upgrade", "open", "low", now),
        (4, "Critical outage", "open", "high", now),
        (5, "Password reset", "open", "low", now),
        (12345, "Account upgrade assistance", "open", "medium", now),
        (12345, "High priority refund review", "open", "high", now),
    ]
    cur.executemany(
        "INSERT INTO tickets (customer_id, issue, status, priority, created_at) VALUES (?,?,?,?,?)",
        tickets
    )
    conn.commit()
    print(f"Database initialized with deterministic test data at {DB}")
    conn.close()


# MCP Server Implementation
class MCPServer:
    """MCP Server that exposes database operations as tools."""
    
    def __init__(self):
        self.tools = {
            "get_customer": self._get_customer_tool,
            "list_customers": self._list_customers_tool,
            "update_customer": self._update_customer_tool,
            "create_ticket": self._create_ticket_tool,
            "get_customer_history": self._get_customer_history_tool,
        }
    
    async def _get_customer_tool(self, customer_id: int):
        """MCP tool: Get customer by ID."""
        conn = db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id=?", (customer_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"success": True, "data": dict(row)}
        return {"success": False, "error": f"Customer {customer_id} not found"}
    
    async def _list_customers_tool(self, status: str = None, limit: int = 100):
        """MCP tool: List customers, optionally filtered by status."""
        conn = db_conn()
        cur = conn.cursor()
        if status:
            cur.execute("SELECT * FROM customers WHERE status=? LIMIT ?", (status, limit))
        else:
            cur.execute("SELECT * FROM customers LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return {"success": True, "data": [dict(r) for r in rows], "count": len(rows)}
    
    async def _update_customer_tool(self, customer_id: int, data: dict):
        """MCP tool: Update customer fields."""
        conn = db_conn()
        cur = conn.cursor()
        
        # Build update query
        allowed_fields = ["name", "email", "phone", "status"]
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            conn.close()
            return {"success": False, "error": "No valid fields to update"}
        
        set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
        params = list(updates.values()) + [datetime.datetime.now(datetime.UTC).isoformat(), customer_id]
        cur.execute(f"UPDATE customers SET {set_clause}, updated_at=? WHERE id=?", params)
        conn.commit()
        
        # Fetch updated record
        cur.execute("SELECT * FROM customers WHERE id=?", (customer_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return {"success": True, "data": dict(row)}
        return {"success": False, "error": f"Customer {customer_id} not found"}
    
    async def _create_ticket_tool(self, customer_id: int, issue: str, priority: str = "medium"):
        """MCP tool: Create a new support ticket."""
        conn = db_conn()
        cur = conn.cursor()
        
        # Validate priority
        if priority.lower() not in ["low", "medium", "high"]:
            conn.close()
            return {"success": False, "error": "Priority must be 'low', 'medium', or 'high'"}
        
        now = datetime.datetime.now(datetime.UTC).isoformat()
        cur.execute(
            "INSERT INTO tickets (customer_id, issue, status, priority, created_at) VALUES (?, ?, ?, ?, ?)",
            (customer_id, issue, "open", priority.lower(), now)
        )
        conn.commit()
        ticket_id = cur.lastrowid
        cur.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return {"success": True, "data": dict(row)}
        return {"success": False, "error": "Failed to create ticket"}
    
    async def _get_customer_history_tool(self, customer_id: int):
        """MCP tool: Get ticket history for a customer."""
        conn = db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tickets WHERE customer_id=? ORDER BY created_at DESC",
            (customer_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return {"success": True, "data": [dict(r) for r in rows], "count": len(rows)}
    
    async def call_tool(self, tool_name: str, **kwargs):
        """Call an MCP tool by name."""
        if tool_name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        try:
            return await self.tools[tool_name](**kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}


# Create MCP server instance
mcp_server = MCPServer()

# MCP Server HTTP endpoints
async def mcp_tools_list(request):
    """List available MCP tools."""
    return JSONResponse({
        "tools": [
            {
                "name": "get_customer",
                "description": "Get customer information by ID",
                "parameters": {"customer_id": "integer"}
            },
            {
                "name": "list_customers",
                "description": "List customers, optionally filtered by status",
                "parameters": {"status": "string (optional)", "limit": "integer (optional)"}
            },
            {
                "name": "update_customer",
                "description": "Update customer fields (name, email, phone, status)",
                "parameters": {"customer_id": "integer", "data": "dict"}
            },
            {
                "name": "create_ticket",
                "description": "Create a new support ticket",
                "parameters": {"customer_id": "integer", "issue": "string", "priority": "string (low/medium/high)"}
            },
            {
                "name": "get_customer_history",
                "description": "Get ticket history for a customer",
                "parameters": {"customer_id": "integer"}
            }
        ]
    })


async def mcp_call_tool(request):
    """Call an MCP tool."""
    try:
        body = await request.json()
        tool_name = body.get("tool")
        params = body.get("params", {})
        
        result = await mcp_server.call_tool(tool_name, **params)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# Create MCP server application
mcp_app = Starlette(routes=[
    Route("/tools", mcp_tools_list, methods=["GET"]),
    Route("/call", mcp_call_tool, methods=["POST"]),
])


if __name__ == "__main__":
    print("Initializing MCP Server...")
    init_db()
    print("\nStarting MCP Server on http://127.0.0.1:8000")
    print("Press Ctrl+C to stop\n")
    
    config = uvicorn.Config(
        mcp_app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())

