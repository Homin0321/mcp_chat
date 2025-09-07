# sse_client.py
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # SSE server URL
    server_url = "http://localhost:8080/sse"
    
    print(f"Connecting to SSE server at {server_url}...")
    
    # Create the connection via SSE transport
    async with sse_client(url=server_url) as streams:
        # Create the client session with the streams
        async with ClientSession(*streams) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            response = await session.list_tools()
            print("Available tools:", [tool.name for tool in response.tools])
            
            # Call the greet tool
            result = await session.call_tool("greet", {"name": "Bob"})
            print("Greeting result:", result.content)
            
            # Call the add tool
            result = await session.call_tool("add", {"a": 10, "b": 32})
            print("Addition result:", result.content)

if __name__ == "__main__":
    asyncio.run(main())if __name__ == “__main__”:
 asyncio.run(main())