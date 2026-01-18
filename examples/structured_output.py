"""Structured output example - get JSON responses with defined schemas.

This example demonstrates using the `output_format` option to receive
structured JSON responses from the agent, making it easy to parse and
use the results programmatically.
"""

import asyncio
import json

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    query,
)

# Define the JSON schema for structured output.
# The agent will format its response to match this schema.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "A brief 1-2 sentence summary of the text",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of main points or takeaways",
        },
        "sentiment": {
            "type": "string",
            "enum": ["positive", "negative", "neutral"],
            "description": "Overall sentiment of the text",
        },
    },
    "required": ["summary", "key_points", "sentiment"],
}

# Sample text for the agent to analyze
SAMPLE_TEXT = """
Modal is a cloud platform that makes it easy to run Python code in the cloud.
It handles all the infrastructure complexity so you can focus on your code.
With Modal, you can run GPU workloads, deploy web endpoints, and schedule jobs
with just a few lines of Python. The platform automatically scales your code
and provides fast cold starts. Developers love how Modal eliminates the need
to manage servers, containers, or Kubernetes clusters.
"""


async def main():
    """Run an agent query with structured JSON output."""
    # Configure the agent with output_format to get structured responses.
    # The output_format option tells the agent to format its final response
    # according to the provided JSON schema.
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        output_format=OUTPUT_SCHEMA,
        system_prompt=(
            "You are a text analysis assistant. When given text to analyze, "
            "provide your analysis in the exact JSON format requested. "
            "Be concise and accurate in your analysis."
        ),
    )

    # Create the prompt asking for analysis
    prompt = f"""Analyze the following text and provide a structured analysis:

{SAMPLE_TEXT}

Return your analysis as JSON matching the required schema with summary, key_points, and sentiment."""

    print("Analyzing text with structured output...")
    print("=" * 50)

    structured_response = None

    async for message in query(prompt, options=options):
        # Handle different message types
        if isinstance(message, SystemMessage):
            print(f"[system] Session: {message.subtype}")

        elif isinstance(message, AssistantMessage):
            # Process each content block in the assistant's response
            for block in message.content:
                if isinstance(block, TextBlock):
                    # With output_format, the text response should be valid JSON
                    text = block.text.strip()
                    if text:
                        try:
                            # Parse the JSON response
                            structured_response = json.loads(text)
                            print("[assistant] Received structured response")
                        except json.JSONDecodeError:
                            # Sometimes the agent may include non-JSON text
                            print(f"[assistant] {text[:100]}...")

        elif isinstance(message, ResultMessage):
            print(f"[result] Completed in {message.num_turns} turns")

    # Use the structured response
    if structured_response:
        print("\n" + "=" * 50)
        print("PARSED STRUCTURED RESPONSE:")
        print("=" * 50)

        print(f"\nSummary:\n  {structured_response.get('summary', 'N/A')}")

        print("\nKey Points:")
        for i, point in enumerate(structured_response.get("key_points", []), 1):
            print(f"  {i}. {point}")

        print(f"\nSentiment: {structured_response.get('sentiment', 'N/A')}")

        # Demonstrate programmatic usage of the structured data
        print("\n" + "=" * 50)
        print("PROGRAMMATIC USAGE:")
        print("=" * 50)

        sentiment = structured_response.get("sentiment")
        if sentiment == "positive":
            print("Action: This text has positive sentiment - consider for marketing!")
        elif sentiment == "negative":
            print("Action: This text has negative sentiment - needs attention.")
        else:
            print("Action: This text is neutral - informational content.")

        num_points = len(structured_response.get("key_points", []))
        print(f"Found {num_points} key points to process.")

    else:
        print("\nNo structured response received.")


if __name__ == "__main__":
    asyncio.run(main())
