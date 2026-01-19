"""Modal compute functions - standalone file for deployment.

This file contains Modal functions that can be deployed and called remotely.
It has no dependencies on modal_agents_sdk to avoid import issues.

Deploy with: modal deploy examples/modal_compute_functions.py
"""

import modal

app = modal.App("agent-compute-tools")


@app.function()
def compute_fibonacci(n: int) -> dict:
    """Compute the nth Fibonacci number.

    Args:
        n: Position in the Fibonacci sequence (0-indexed).

    Returns:
        Dict with the Fibonacci number and input n.
    """

    def fib(x: int) -> int:
        if x <= 1:
            return x
        return fib(x - 1) + fib(x - 2)

    result = fib(min(n, 35))  # Limit to avoid excessive recursion
    return {"fibonacci": result, "n": n}
