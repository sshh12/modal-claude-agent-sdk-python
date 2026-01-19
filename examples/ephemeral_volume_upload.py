"""Ephemeral volume upload example - upload files to sandbox efficiently.

This example demonstrates using Modal's ephemeral volumes with batch_upload
to efficiently transfer local files into the sandbox for processing.

Use cases:
- Upload datasets for analysis
- Provide configuration files
- Send source code for review/modification
- Transfer assets for processing
"""

import asyncio
import io
import json

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def main():
    """Upload files to sandbox and have agent process them."""

    print("Modal Agents SDK - Ephemeral Volume Upload Example")
    print("=" * 50)

    # Create sample data to upload
    sample_data = {
        "employees": [
            {"name": "Alice", "department": "Engineering", "salary": 95000},
            {"name": "Bob", "department": "Sales", "salary": 75000},
            {"name": "Charlie", "department": "Engineering", "salary": 105000},
            {"name": "Diana", "department": "Marketing", "salary": 80000},
            {"name": "Eve", "department": "Engineering", "salary": 90000},
        ]
    }

    sample_config = """
[analysis]
include_statistics = true
group_by = department
output_format = markdown

[filters]
min_salary = 0
departments = all
"""

    analysis_script = '''
"""Analyze employee data from JSON file."""
import json
from collections import defaultdict

def main():
    # Load data
    with open("/input/employees.json") as f:
        data = json.load(f)

    # Group by department
    by_dept = defaultdict(list)
    for emp in data["employees"]:
        by_dept[emp["department"]].append(emp["salary"])

    # Print analysis
    print("## Salary Analysis by Department")
    print()

    total_employees = 0
    total_salaries = 0

    for dept, salaries in sorted(by_dept.items()):
        avg = sum(salaries) / len(salaries)
        total_employees += len(salaries)
        total_salaries += sum(salaries)

        print(f"### {dept}")
        print(f"- Employees: {len(salaries)}")
        print(f"- Average Salary: ${avg:,.2f}")
        print(f"- Total Payroll: ${sum(salaries):,.2f}")
        print()

    print("### Overall")
    print(f"- Total Employees: {total_employees}")
    print(f"- Company Payroll: ${total_salaries:,.2f}")
    print(f"- Company Average: ${total_salaries/total_employees:,.2f}")

if __name__ == "__main__":
    main()
'''

    # Use ephemeral volume for file transfer
    with modal.Volume.ephemeral() as vol:
        print("Uploading files to ephemeral volume...")

        # Batch upload files efficiently
        with vol.batch_upload() as batch:
            # Upload JSON data
            batch.put_file(
                io.BytesIO(json.dumps(sample_data, indent=2).encode()),
                "/input/employees.json"
            )
            # Upload config file
            batch.put_file(
                io.BytesIO(sample_config.encode()),
                "/input/config.ini"
            )
            # Upload the analysis script
            batch.put_file(
                io.BytesIO(analysis_script.encode()),
                "/input/analyze.py"
            )

        print("Files uploaded successfully!")
        print("  - /input/employees.json")
        print("  - /input/config.ini")
        print("  - /input/analyze.py")
        print()

        # Configure agent with the volume mounted
        options = ModalAgentOptions(
            volumes={"/input": vol},
            secrets=[modal.Secret.from_name("anthropic-key")],
            allowed_tools=["Bash", "Read", "Write"],
            system_prompt=(
                "You have access to uploaded files in /input/. "
                "Help the user analyze and process these files."
            ),
        )

        print("Running agent to process uploaded files...")
        print("-" * 50)

        async for message in query(
            "I've uploaded some files to /input/. Please:\n"
            "1. List what files are available in /input/\n"
            "2. Show me the structure of the employees.json data\n"
            "3. Run the analyze.py script and show the results\n"
            "4. Based on the analysis, which department has the highest average salary?",
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[tool] {block.name}")
            elif isinstance(message, ResultMessage):
                print(f"\n[{message.subtype}] Completed in {message.num_turns} turns")

    print("\n" + "=" * 50)
    print("Ephemeral volume example complete!")
    print()
    print("Key features demonstrated:")
    print("  - modal.Volume.ephemeral(): Temporary volume for file transfer")
    print("  - batch_upload(): Efficient multi-file upload")
    print("  - Volume mounting: Files accessible at /input/ in sandbox")
    print("  - Automatic cleanup: Volume deleted when context exits")


if __name__ == "__main__":
    asyncio.run(main())
