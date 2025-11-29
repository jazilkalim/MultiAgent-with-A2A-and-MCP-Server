# Assignment 5 - Multi-Agent Customer Service System with A2A and MCP

## Overview

This project implements a multi-agent customer service system using Google's Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP). The system consists of three specialized agents that coordinate to handle customer service requests:

1. **Router Agent** - Orchestrates requests and routes them to appropriate specialist agents
2. **Customer Data Agent** - Manages customer information via MCP
3. **Support Agent** - Handles support tickets and customer service requests via MCP

## Architecture

### System Components

- **A2A Protocol**: Enables agent-to-agent communication using standardized JSON-RPC protocol
- **MCP Server**: Provides database access through standardized tools (running on port 8000)
- **Three Agent System**: Router, Customer Data, and Support agents running as A2A servers

### MCP Tools

The MCP server exposes the following tools:
- `get_customer(customer_id)` - Retrieve customer information
- `list_customers(status, limit)` - List customers with optional status filter
- `update_customer(customer_id, data)` - Update customer fields
- `create_ticket(customer_id, issue, priority)` - Create support tickets
- `get_customer_history(customer_id)` - Get ticket history for a customer

### A2A Coordination Scenarios

1. **Task Allocation**: Router receives query → Routes to appropriate agent → Returns response
2. **Negotiation/Escalation**: Router detects multiple intents → Coordinates between agents → Formulates coordinated response
3. **Multi-Step Coordination**: Router decomposes complex query → Calls multiple agents sequentially → Synthesizes final answer

## Prerequisites

- Python 3.11+
- Virtual environment (recommended)
- Google Cloud Project with Vertex AI enabled (for Gemini models)
- MCP Server running on port 8000

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Assignment5/HW
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1  # Windows PowerShell
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Set `GOOGLE_API_KEY` in your environment or use Google Colab's userdata
   - Configure `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` if using Vertex AI

## Running the System

### Step 1: Start MCP Server

In a separate terminal, start the MCP server:
```bash
python ../mcp_server_standalone.py
```

The MCP server will run on `http://127.0.0.1:8000`

### Step 2: Run the Notebook

1. Open `HW.ipynb` in Jupyter Notebook or Google Colab
2. Run all cells in order
3. The system will:
   - Initialize the database
   - Create all agents
   - Start A2A servers on ports 9300, 9301, and 9400
   - Run test scenarios

### Step 3: Test Scenarios

The notebook includes 7 test scenarios:
1. Simple Query - Get Customer Information
2. Coordinated Query - Account Upgrade
3. Complex Query - Active Customers with Open Tickets
4. Escalation - Refund Request
5. Multi-Intent - Update and History
6. List Active Customers
7. Ticket History

## Project Structure

```
HW/
├── HW.ipynb              # Main notebook with complete implementation
├── README.md             # This file
└── requirements.txt      # Python dependencies

../
├── assignment5_complete.py    # Complete Python implementation (reference)
├── mcp_server_standalone.py  # MCP server implementation
├── test_mcp.py               # MCP server test script
└── database_setup.py         # Database setup reference
```

## Key Features

✅ **MCP Integration**: All database operations go through MCP server  
✅ **A2A Coordination**: Router agent uses A2A protocol to communicate with other agents  
✅ **Explicit Logging**: Shows agent-to-agent communication flows  
✅ **Three Coordination Scenarios**: Task allocation, negotiation, and multi-step coordination  
✅ **Comprehensive Testing**: 7 test scenarios covering all requirements  

## Database Schema

### Customers Table
- `id` (INTEGER PRIMARY KEY)
- `name` (TEXT)
- `email` (TEXT)
- `phone` (TEXT)
- `status` (TEXT: 'active' or 'disabled')
- `created_at` (TEXT)
- `updated_at` (TEXT)

### Tickets Table
- `id` (INTEGER PRIMARY KEY)
- `customer_id` (INTEGER, FK to customers.id)
- `issue` (TEXT)
- `status` (TEXT: 'open', 'in_progress', 'resolved')
- `priority` (TEXT: 'low', 'medium', 'high')
- `created_at` (TEXT)

## A2A Server Endpoints

- **CustomerDataAgent**: `http://127.0.0.1:9300`
- **SupportAgent**: `http://127.0.0.1:9301`
- **RouterAgent**: `http://127.0.0.1:9400`

Each agent exposes its capabilities via `.well-known/agent-card.json`

## Troubleshooting

### MCP Server Not Reachable
- Ensure MCP server is running on port 8000
- Check firewall settings
- Verify `mcp_client` URL in code matches server URL

### Agents Not Responding
- Check that all A2A servers started successfully
- Verify ports 9300, 9301, 9400 are not in use
- Check logs for error messages

### Database Issues
- Database is created automatically on first run
- If issues occur, delete `mcp.db` and rerun the database setup cell

## Assignment Requirements Met

- ✅ **Part 1**: Three-agent system architecture (Router, Customer Data, Support)
- ✅ **Part 2**: MCP integration with all 5 required tools
- ✅ **Part 3**: A2A coordination with all 3 required scenarios
- ✅ **Test Scenarios**: All required test cases implemented
- ✅ **Logging**: Explicit agent-to-agent communication logging
- ✅ **Documentation**: Complete README and code comments

## Learning Outcomes

This project demonstrates:
- Multi-agent system design and orchestration
- A2A protocol implementation for agent communication
- MCP integration for standardized tool access
- Task allocation and negotiation patterns
- Multi-step coordination workflows

## Author

[Your Name]

## License

This project is for educational purposes as part of the Applied Generative AI Agents and Multimodal Intelligence course.

