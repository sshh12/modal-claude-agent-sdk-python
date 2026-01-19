"""Tunnel and port forwarding example - agent builds and runs a web app.

This example demonstrates:
- Having an agent build a Flask web server from scratch
- Running the server inside a Modal sandbox
- Accessing the web app via Modal's encrypted tunnel from the host machine

The key insight is that we trust the agent to build and run the server,
then verify it works by accessing the tunnel from outside.
"""

import asyncio
import time

import modal
import requests

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentClient,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

# Port the agent will use for the Flask server
SERVER_PORT = 5000


async def main():
    """Have an agent build and run a Flask web server, then access it via tunnel."""

    print("Modal Agents SDK - Tunnel Web App Example")
    print("=" * 60)
    print()
    print("This example will:")
    print("1. Ask an agent to build a Flask web server")
    print("2. Have the agent run the server on port 5000")
    print("3. Access the server via Modal's encrypted tunnel")
    print("4. Keep the server running for verification")
    print()

    # Configure the agent with tunnel support
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Bash", "Read", "Write"],
        encrypted_ports=[SERVER_PORT],
        timeout=300,  # 5 minute timeout
        system_prompt="""You are a helpful assistant that can write and run code.
When asked to run a server, use 'nohup' and '&' to run it in the background
so it keeps running after the command returns.""",
    )

    # Prompt for the agent
    agent_prompt = f"""
Please do the following:

1. Create a simple Flask web application in /workspace/app.py with these endpoints:
   - GET / : Returns a JSON response with {{"message": "Hello from Modal sandbox!", "status": "running"}}
   - GET /health : Returns {{"healthy": true}}
   - GET /info : Returns {{"port": {SERVER_PORT}, "framework": "flask"}}

2. Install Flask if needed using pip

3. Start the Flask server on port {SERVER_PORT}, binding to 0.0.0.0 so it's accessible externally.
   IMPORTANT: Run it in the background using nohup so it keeps running:
   nohup python /workspace/app.py > /workspace/server.log 2>&1 &

4. Wait a moment and verify the server is running by checking the process list or curling localhost

5. Report that the server is ready
"""

    print("Step 1: Starting agent to build and run the web server...")
    print("-" * 60)

    async with ModalAgentClient(options=options) as client:
        # Send the prompt to the agent
        await client.query(agent_prompt)

        # Process agent responses
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        # Show agent's text output (truncated if long)
                        text = block.text
                        print(text[:500] + "..." if len(text) > 500 else text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[tool] {block.name}: {str(block.input)[:100]}...")
                    elif isinstance(block, ToolResultBlock):
                        # Show abbreviated tool results
                        content = str(block.content)[:200]
                        status = "error" if block.is_error else "ok"
                        print(f"[result:{status}] {content}...")
            elif isinstance(msg, ResultMessage):
                print(f"\n[{msg.subtype}] Agent finished")

        print()
        print("Step 2: Getting tunnel URL...")
        print("-" * 60)

        # Get the tunnel for our port
        tunnels = client.tunnels()

        if SERVER_PORT not in tunnels:
            print(f"ERROR: No tunnel available on port {SERVER_PORT}")
            print(f"Available tunnels: {list(tunnels.keys())}")
            return

        tunnel = tunnels[SERVER_PORT]
        tunnel_url = tunnel.url
        print(f"Tunnel URL: {tunnel_url}")

        print()
        print("Step 3: Testing the web server via tunnel...")
        print("-" * 60)

        # Give the server a moment to be fully ready
        print("Waiting for server to be fully ready...")
        time.sleep(3)

        # Test each endpoint
        test_passed = True
        endpoints = ["/", "/health", "/info"]

        for endpoint in endpoints:
            url = f"{tunnel_url}{endpoint}"
            print(f"\nGET {endpoint}:")
            try:
                response = requests.get(url, timeout=15)
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.json()}")
                else:
                    print(f"  Response: {response.text[:200]}")
                    test_passed = False
            except requests.RequestException as e:
                print(f"  ERROR: {e}")
                test_passed = False

        print()
        print("=" * 60)

        if test_passed:
            print("SUCCESS: All endpoints accessible via tunnel!")
        else:
            print("WARNING: Some endpoints failed")

        print()
        print(f"Web server is running at: {tunnel_url}")
        print()

        # Keep the server running for a bit so user can manually test
        print("Step 4: Keeping server alive for manual testing...")
        print("-" * 60)
        print("Server will stay running for 60 seconds.")
        print("You can test it manually in your browser or with curl.")
        print()

        # Poll the health endpoint periodically to show it's still working
        for i in range(6):
            time.sleep(10)
            remaining = 60 - (i + 1) * 10
            try:
                response = requests.get(f"{tunnel_url}/health", timeout=5)
                status = "healthy" if response.status_code == 200 else "unhealthy"
            except requests.RequestException:
                status = "unreachable"
            print(f"  [{remaining}s remaining] Server status: {status}")

        print()
        print("Shutting down sandbox...")

    # Client context manager handles cleanup

    print()
    print("=" * 60)
    print("Tunnel example complete!")
    print()
    print("Key features demonstrated:")
    print("  - encrypted_ports: Expose ports via HTTPS tunnel")
    print("  - client.tunnels(): Get tunnel URLs for exposed ports")
    print("  - Agent-built server: Let the agent write and run the code")
    print("  - External access: Access sandbox services from host machine")


if __name__ == "__main__":
    asyncio.run(main())
