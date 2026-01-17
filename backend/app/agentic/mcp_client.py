"""
MCP Client for agentic AI system
Connects to the MCP server (running in Node.js) and provides tool access
"""

import json
import subprocess
import asyncio
from typing import Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.session import ClientSession


class MCPToolClient:
    """Client for interacting with MCP tools server"""

    def __init__(self, server_script_path: str):
        """
        Initialize MCP client
        
        Args:
            server_script_path: Path to the mcp-server.ts file (e.g., ../express-api/src/mcp-server.ts)
        """
        self.server_script_path = server_script_path
        self.session: Optional[ClientSession] = None

    async def connect(self) -> None:
        """Connect to the MCP server"""
        try:
            # Start the MCP server as a subprocess
            # ts-node will run the TypeScript directly
            server_params = StdioServerParameters(
                command="ts-node",
                args=[self.server_script_path],
            )

            # Create a session with the server
            self.session = ClientSession(server_params)
            await self.session.initialize()
            print("✅ Connected to MCP tools server")

        except Exception as e:
            print(f"❌ Failed to connect to MCP server: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server"""
        if self.session:
            await self.session.close()
            print("✅ Disconnected from MCP tools server")

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        List all available tools from the MCP server
        
        Returns:
            List of tool definitions with name, description, and inputSchema
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        tools = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
            for tool in tools
        ]

    async def call_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            tool_input: Dictionary of arguments for the tool
            
        Returns:
            Result from the tool execution
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        try:
            result = await self.session.call_tool(tool_name, tool_input)
            
            # Extract the text content from the result
            if result.content and len(result.content) > 0:
                text_content = result.content[0].text
                # Parse the JSON response
                return json.loads(text_content)
            
            return {"success": False, "error": "No response from tool"}

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


# For testing the client
async def test_mcp_client():
    """Test the MCP client with sample operations"""
    client = MCPToolClient("/Users/senthilkumar/git/rag-prac/express-api/src/mcp-server.ts")

    async with client:
        # List available tools
        print("\n📋 Available Tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

        # Test: List users
        print("\n🔍 Calling list_users tool:")
        result = await client.call_tool("list_users", {})
        print(f"  Result: {json.dumps(result, indent=2)}")

        # Test: Get user
        print("\n🔍 Calling get_user tool:")
        result = await client.call_tool("get_user", {"user_id": "user1"})
        print(f"  Result: {json.dumps(result, indent=2)}")

        # Test: List tasks
        print("\n🔍 Calling list_tasks tool:")
        result = await client.call_tool("list_tasks", {})
        print(f"  Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_mcp_client())
