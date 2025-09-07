import os
import sys
import asyncio
import json
from dotenv import load_dotenv
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
import streamlit as st

st.set_page_config(page_title="MCP Chat", page_icon="🤖", layout="wide")

load_dotenv()
client = genai.Client()

# Load server parameters from mcp.json
@st.cache_data
def load_mcp_config():
    try:
        with open('mcp.json') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Could not find the mcp.json file.")
        st.stop()
    except json.JSONDecodeError:
        st.error("The mcp.json file format is incorrect.")
        st.stop()

mcp_config = load_mcp_config()

server_names = list(mcp_config['mcpServers'].keys())
selected_server = st.sidebar.selectbox("Select a MCP server", server_names)
server_config = mcp_config['mcpServers'][selected_server]

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command=server_config['command'],
    args=server_config['args'],
    env=server_config.get('env'),
)

# Server configuration details
with st.sidebar.expander("⚙️ MCP Server Configuration"):
    st.json(server_config)

async def inspect_server(session):
    with st.sidebar.expander("🔎 MCP Server Inspection"):
        # Prompts
        st.subheader("📑 Prompts")
        try:
            prompts = await session.list_prompts()
            if prompts and prompts.prompts:
                st.markdown("\n".join([f"- **{p.name}**" for p in prompts.prompts]))
            else:
                st.info("No prompts available.")
        except Exception as e:
            st.warning(f"list_prompts not supported: {e}")

        # Resources
        st.subheader("📂 Resources")
        try:
            resources = await session.list_resources()
            if resources and resources.resources:
                st.markdown("\n".join([f"- `{r.uri}`" for r in resources.resources]))
            else:
                st.info("No resources available.")
        except Exception as e:
            st.warning(f"list_resources not supported: {e}")

        # Tools
        st.subheader("🛠️ Tools")
        try:
            tools = await session.list_tools()
            if tools and tools.tools:
                st.markdown("\n".join([f"- **{t.name}**" for t in tools.tools]))
            else:
                st.info("No tools available.")
        except Exception as e:
            st.warning(f"list_tools not supported: {e}")

async def send_prompt(prompt):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    tools=[session],
                ),
            )
            with st.chat_message("assistant"):
                st.markdown(response.text)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response.text})

# Session initialization and server inspection
async def init_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await inspect_server(session)

# Whenever the selected_server changes, re-initialize session and inspect server
if ("selected_server" not in st.session_state) or (st.session_state.selected_server != selected_server):
    asyncio.run(init_session())
    st.session_state.selected_server = selected_server
    st.session_state.messages = []

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title(f"MCP Chat - {selected_server}")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        asyncio.run(send_prompt(prompt))
    except* Exception as eg:
        for e in eg.exceptions:
            st.error(f"Caught exception: {repr(e)}")