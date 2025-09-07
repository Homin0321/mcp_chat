# stdio_client.py
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Get the server script path (same directory as this file)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "stdio_server.py")
    
    # Create server parameters
    server_params = StdioServerParameters(
        command="python",
        args=[server_path]
    )
    
    # Create the connection via stdio transport
    async with stdio_client(server_params) as streams:
        # Create the client session with the streams
        async with ClientSession(*streams) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            response = await session.list_tools()
            print("Available tools:", [tool.name for tool in response.tools])
            
            # Call the greet tool
            result = await session.call_tool("greet", {"name": "Alice"})
            print("Greeting result:", result.content)
            
            # Call the add tool
            result = await session.call_tool("add", {"a": 5, "b": 7})
            print("Addition result:", result.content)

if __name__ == "__main__":
    asyncio.run(main())