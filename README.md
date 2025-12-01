# Assignment 5 - Multi-Agent Customer Service System with A2A and MCP

## Overview

This project implements a multi-agent customer service system using Google's Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP). The system consists of three specialized agents that coordinate to handle customer service requests:

1. **Router Agent** - Orchestrates requests and routes them to appropriate specialist agents
2. **Customer Data Agent** - Manages customer information via MCP tools
3. **Support Agent** - Handles support tickets and customer service requests via MCP tools

## Prerequisites

- Python 3.11+
- Virtual environment (recommended)
- Google Cloud Project with Vertex AI enabled (for Gemini models)
- MCP Server running on port 8000

## Installation

1. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google API credentials** (choose one option):
   
   **Option A: Google AI API (Recommended for local development)**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a `.env` file in the HW folder:
     ```
     GOOGLE_API_KEY=your_api_key_here
     ```
   - Or set environment variable:
     ```bash
     export GOOGLE_API_KEY=your_api_key_here  # Linux/Mac
     set GOOGLE_API_KEY=your_api_key_here     # Windows CMD
     $env:GOOGLE_API_KEY="your_api_key_here"  # Windows PowerShell
     ```
   
   **Option B: Vertex AI (For production/Cloud)**
   - Set environment variables:
     ```bash
     export GOOGLE_CLOUD_PROJECT=your-project-id
     export GOOGLE_CLOUD_LOCATION=us-central1
     ```
   - Authenticate with: `gcloud auth application-default login`

## Running the System

### Step 1: Start the MCP Server

The MCP server must be running before starting the agents. Start it in a separate terminal:

```bash
python mcp_server_standalone.py
```

The MCP server will run on `http://127.0.0.1:8000`

### Step 2: Run the Complete System

Run the main implementation file:

```bash
python assignment5_fixed_complete.py
```

This will:
- Create and seed the database with test data
- Start all three agent servers:
  - Customer Data Agent: `http://127.0.0.1:9300`
  - Support Agent: `http://127.0.0.1:9301`
  - Router Agent: `http://127.0.0.1:9400`
- Run all test scenarios automatically

### Alternative: Run from Jupyter Notebook

1. Open `HW.ipynb` in Jupyter
2. Copy code from `assignment5_fixed_complete.py` into notebook cells
3. Run cells sequentially

## Test Scenarios

The system includes 5 test scenarios:

1. **Simple Query** - Get customer information for ID 1
2. **Coordinated Query** - Account upgrade request for customer ID 2
3. **Complex Query** - Show all active customers with open tickets
4. **Escalation** - Refund request for customer ID 1
5. **Multi-Intent** - Update email and show ticket history for customer ID 5

## Project Structure

```
HW/
├── assignment5_fixed_complete.py  # Main implementation (complete system)
├── mcp_tools.py                   # MCP tool wrappers for ADK agents
├── a2a_agents_fixed.py           # Agent definitions
├── HW.ipynb                       # Jupyter notebook (optional)
├── README.md                      # This file
├── requirements.txt               # Python dependencies
└── mcp.db                         # SQLite database (auto-created)
```

## Key Features

- **MCP Integration**: All database operations go through MCP server tools
- **A2A Coordination**: Router agent uses A2A protocol to communicate with specialist agents
- **LLM-Based Tool Selection**: Agents use LLM reasoning to select appropriate MCP tools
- **Three Coordination Scenarios**: Task allocation, negotiation, and multi-step coordination

## Troubleshooting

### MCP Server Not Reachable
- Ensure MCP server is running on port 8000
- Check firewall settings
- Verify MCP server URL in code matches server URL

### Agents Not Responding
- Check that all A2A servers started successfully
- Verify ports 9300, 9301, 9400 are not in use
- Check logs for error messages

### Database Issues
- Database is created automatically on first run
- If issues occur, delete `mcp.db` and rerun the script

## Notes

- The MCP server must be running before starting agents
- All agents use MCP tools for database operations (no direct database access)
- Customer IDs in test data: 1, 2, 3, 4, 5, 12345
