#!/usr/bin/env python3
"""Code Execution MCP Server - Using FastMCP."""
import os
from fastmcp import FastMCP
from code_execution_tool import CodeExecutionTool
from helpers.clean_string import clean_string

# Read configuration from environment
EXECUTABLE = os.environ.get("EXECUTABLE", "/bin/bash")
INIT_COMMANDS_STR = os.environ.get("INIT_COMMANDS", "")
INIT_COMMANDS = [cmd.strip() for cmd in INIT_COMMANDS_STR.split(";") if cmd.strip()] if INIT_COMMANDS_STR else []

# Timeout options
OPTIONS = {
    "first_output_timeout": int(os.environ.get("FIRST_OUTPUT_TIMEOUT", "30")),
    "between_output_timeout": int(os.environ.get("BETWEEN_OUTPUT_TIMEOUT", "15")),
    "dialog_timeout": int(os.environ.get("DIALOG_TIMEOUT", "5")),
    "max_exec_timeout": int(os.environ.get("MAX_EXEC_TIMEOUT", "180")),
}

# Initialize FastMCP server
mcp = FastMCP("code-execution-mcp")

# Initialize code execution tool
code_tool = CodeExecutionTool(executable=EXECUTABLE, init_commands=INIT_COMMANDS, options=OPTIONS)


@mcp.tool()
async def execute_terminal(command: str, session: int = 0) -> str:
    """Execute a terminal command in the specified session.

    Automatically exits Python mode if the session is currently running a Python REPL.
    Note: Exiting Python mode clears all Python state (variables, imports).
    For persistent Python state, use a dedicated session for Python work.

    Args:
        command: The terminal command to execute
        session: Session number (default: 0)

    Returns:
        Clean output without ANSI codes
    """
    result = await code_tool.execute_terminal_command(session=session, command=command)
    return clean_string(result)


@mcp.tool()
async def execute_python(code: str, session: int = 0) -> str:
    """Execute Python code in a persistent Python REPL.

    The first call on a session starts a Python REPL (python3 -i).
    Subsequent calls on the same session reuse the REPL, maintaining state.
    Variables, imports, and function definitions persist across calls.

    If you later call execute_terminal on this session, the Python REPL will be
    automatically exited, clearing all Python state.

    Args:
        code: The Python code to execute
        session: Session number (default: 0)

    Returns:
        Clean output without ANSI codes
    """
    result = await code_tool.execute_python_code(session=session, code=code)
    return clean_string(result)


@mcp.tool()
async def get_output(session: int = 0) -> str:
    """Get accumulated output from a terminal session without clearing the buffer.

    Useful for checking on long-running processes or retrieving output history.
    Note: Command outputs are typically included in execute_terminal and execute_python
    responses, so this tool is mainly needed for polling long-running background tasks.

    Args:
        session: Session number (default: 0)

    Returns:
        Clean output without ANSI codes
    """
    result = await code_tool.get_terminal_output(session=session, reset_full_output=False)
    return clean_string(result)


@mcp.tool()
async def reset_terminal(session: int = 0) -> str:
    """Reset a terminal session, closing and reopening it.

    This completely clears the session state including:
    - Python REPL state (variables, imports, functions)
    - Shell environment variables set during the session
    - Working directory (returns to initial directory)

    Useful when:
    - A session is stuck or unresponsive
    - You want to start with a clean slate
    - You need to clear all state manually

    Args:
        session: Session number (default: 0)

    Returns:
        Confirmation message
    """
    result = await code_tool.reset_terminal(session=session)
    return clean_string(result)


if __name__ == "__main__":
    # Run the MCP server via stdio
    mcp.run()
