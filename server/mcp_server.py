import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from tools import get_energy_baseline, compare_current_vs_baseline, assess_measure_effectiveness, draft_management_review_section

# Initialize MCP server
server = Server("iso50001-energy-baseline")

@server.list_tools()
async def list_tools():
    return [
        {
            "name": "get_energy_baseline",
            "description": "Get energy baseline data for a facility and year",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "facility_id": {"type": "string", "description": "Facility ID (e.g., FAC-001)"},
                    "year": {"type": "integer", "description": "Baseline year", "default": 2022}
                },
                "required": ["facility_id"]
            }
        },
        {
            "name": "compare_current_vs_baseline", 
            "description": "Compare current consumption vs baseline for a period",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "facility_id": {"type": "string", "description": "Facility ID"},
                    "period": {"type": "string", "description": "Period format: YYYY-Q1, YYYY-Q2, YYYY-Q3, YYYY-Q4, or YYYY-full"}
                },
                "required": ["facility_id", "period"]
            }
        },
        {
            "name": "assess_measure_effectiveness",
            "description": "Assess if an energy-saving measure met projected savings",
            "inputSchema": {
                "type": "object", 
                "properties": {
                    "measure_id": {"type": "string", "description": "Energy measure ID (e.g., MSR-001)"}
                },
                "required": ["measure_id"]
            }
        },
        {
            "name": "draft_management_review_section",
            "description": "Draft ISO 50001 management review section using LLM",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "facility_id": {"type": "string", "description": "Facility ID"},
                    "period": {"type": "string", "description": "Review period (YYYY-Q1, YYYY-Q2, etc.)"}
                },
                "required": ["facility_id", "period"]
            }
        }
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "get_energy_baseline":
            result = get_energy_baseline(
                arguments["facility_id"], 
                arguments.get("year", 2022)
            )
        elif name == "compare_current_vs_baseline":
            result = compare_current_vs_baseline(
                arguments["facility_id"],
                arguments["period"]
            )
        elif name == "assess_measure_effectiveness":
            result = assess_measure_effectiveness(arguments["measure_id"])
        elif name == "draft_management_review_section":
            result = draft_management_review_section(
                arguments["facility_id"],
                arguments["period"]
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(
            type="text", 
            text=json.dumps(result, indent=2)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    async with stdio_server() as streams:
        await server.run(*streams)

if __name__ == "__main__":
    asyncio.run(main())
