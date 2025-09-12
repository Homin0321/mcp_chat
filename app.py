import os
import asyncio
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
import streamlit as st

# Page settings
st.set_page_config(page_title="MCP Chat", page_icon="🤖", layout="wide")

# Load environment variables and initialize client
@st.cache_resource
def initialize_genai_client():
    """Initialize Gemini AI client."""
    load_dotenv()
    return genai.Client()

client = initialize_genai_client()

# Chat management functions
def create_new_chat():
    """Create a new chat session."""
    st.session_state.chat = {
        'messages': [],
        'server': st.session_state.get('selected_server', 'None')
    }

# Load config file
@st.cache_data
def load_mcp_config() -> Dict[str, Any]:
    """Load MCP configuration file."""
    config_path = 'mcp.json'
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        if 'mcpServers' not in config:
            raise ValueError("Config file does not contain 'mcpServers' key.")
            
        return config
    except FileNotFoundError:
        st.error(f"Config file not found: {config_path}")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format: {e}")
        st.stop()
    except ValueError as e:
        st.error(f"Configuration file error: {e}")
        st.stop()

def validate_server_config(config: Dict[str, Any]) -> bool:
    """Validate server configuration."""
    required_fields = ['command', 'args']
    for field in required_fields:
        if field not in config:
            st.error(f"Missing required field in server configuration: {field}")
            return False
    return True

def create_server_parameters(server_config: Dict[str, Any]) -> StdioServerParameters:
    """Create server parameters."""
    if not validate_server_config(server_config):
        raise ValueError("Invalid server configuration")
    
    return StdioServerParameters(
        command=server_config['command'],
        args=server_config['args'],
        env=server_config.get('env'),
    )

async def safe_inspect_server(session: ClientSession):
    """Safely inspect the server."""
    with st.sidebar.expander("🔎 MCP Server Inspection"):
        # Prompts inspection
        st.subheader("📑 Prompts")
        try:
            prompts = await asyncio.wait_for(session.list_prompts(), timeout=5.0)
            if prompts and prompts.prompts:
                prompt_list = [f"- **{p.name}**: {p.description or 'No description'}" for p in prompts.prompts]
                st.markdown("\n".join(prompt_list))
            else:
                st.info("No available prompts.")
        except asyncio.TimeoutError:
            st.warning("Prompt list request timed out")
        except Exception as e:
            st.warning(f"Unable to fetch prompt list: {e}")

        # Resources inspection
        st.subheader("📂 Resources")
        try:
            resources = await asyncio.wait_for(session.list_resources(), timeout=5.0)
            if resources and resources.resources:
                resource_list = [f"- `{r.uri}`: {r.name or 'No name'}" for r in resources.resources]
                st.markdown("\n".join(resource_list))
            else:
                st.info("No available resources.")
        except asyncio.TimeoutError:
            st.warning("Resource list request timed out")
        except Exception as e:
            st.warning(f"Unable to fetch resource list: {e}")

        # Tools inspection
        st.subheader("🛠️ Tools")
        try:
            tools = await asyncio.wait_for(session.list_tools(), timeout=5.0)
            if tools and tools.tools:
                tool_list = [f"- **{t.name}**: {t.description or 'No description'}" for t in tools.tools]
                st.markdown("\n".join(tool_list))
            else:
                st.info("No available tools.")
        except asyncio.TimeoutError:
            st.warning("Tool list request timed out")
        except Exception as e:
            st.warning(f"Unable to fetch tool list: {e}")

@asynccontextmanager
async def get_mcp_session(server_params: Optional[StdioServerParameters]):
    """Context manager for safely managing MCP session."""
    if not server_params:
        yield None
        return
        
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                yield session
    except asyncio.TimeoutError:
        st.error("MCP server connection timed out")
        yield None
    except Exception as e:
        st.error(f"Failed to connect to MCP server: {e}")
        yield None

async def send_message_with_mcp(prompt: str, server_params: Optional[StdioServerParameters]):
    """Send message with MCP server using Gemini chat."""
    try:
        async with get_mcp_session(server_params) as session:
            # Get conversation history for context
            messages = st.session_state.chat['messages']
            
            # Prepare full conversation context including the current prompt
            contents = []
            for msg in messages:
                if msg['role'] == 'user':
                    contents.append({
                        'role': 'user',
                        'parts': [{'text': msg['content']}]
                    })
                elif msg['role'] == 'assistant':
                    contents.append({
                        'role': 'model',
                        'parts': [{'text': msg['content']}]
                    })
            
            # Add current user prompt
            contents.append({
                'role': 'user',
                'parts': [{'text': prompt}]
            })
            
            # Create configuration with tools if available
            config = genai.types.GenerateContentConfig()
            if session is not None:
                config.tools = [session]
            
            with st.spinner("Generating response..."):
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model="gemini-2.0-flash-exp",
                        contents=contents,
                        config=config,
                    ),
                    timeout=30.0
                )
            
            if response and response.text:
                with st.chat_message("assistant"):
                    st.markdown(response.text)
                st.session_state.chat['messages'].append({
                    'role': 'assistant',
                    'content': response.text
                })
            else:
                st.warning("Received empty response.")
                
    except asyncio.TimeoutError:
        st.error("Response generation timed out.")
    except Exception as e:
        st.error(f"Error occurred while sending message: {e}")

async def initialize_session_safely(server_params: Optional[StdioServerParameters]):
    """Safely initialize session."""
    if not server_params:
        return
    
    try:
        async with get_mcp_session(server_params) as session:
            if session:
                await safe_inspect_server(session)
    except Exception as e:
        st.error(f"Error during session initialization: {e}")

def main():
    """Main application function."""
    # MCP Server configuration in sidebar
    with st.sidebar:
        st.header("MCP Chat")
        
        if 'chat' not in st.session_state:
            create_new_chat()
            st.rerun()

        # New chat button
        if st.button("New Chat", use_container_width=True):
            create_new_chat()
            st.rerun()

        # Load MCP configuration
        mcp_config = load_mcp_config()
        
        # Server selection
        server_names = ["None"] + list(mcp_config['mcpServers'].keys())
        selected_server = st.selectbox("Select MCP Server", server_names)
        
        # Get server configuration
        server_config = {} if selected_server == "None" else mcp_config['mcpServers'][selected_server]
        server_params = None
        
        if server_config:
            try:
                server_params = create_server_parameters(server_config)
            except ValueError as e:
                st.error(f"Server configuration error: {e}")
                server_params = None
        
        # Display server configuration
        with st.expander("Server Configuration"):
            if server_config:
                st.json(server_config)
            else:
                st.info("No server selected.")
    
    # Reinitialize session on server change
    if ("selected_server" not in st.session_state) or (st.session_state.selected_server != selected_server):
        with st.spinner("Connecting to server..."):
            asyncio.run(initialize_session_safely(server_params))
        st.session_state.selected_server = selected_server
    
    # Display chat history
    messages = st.session_state.chat['messages']
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Handle user input
    if prompt := st.chat_input("Enter your message..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add user message to current chat
        st.session_state.chat['messages'].append({
            'role': 'user',
            'content': prompt
        })
        
        # Generate response
        asyncio.run(send_message_with_mcp(prompt, server_params))

if __name__ == "__main__":
    main()