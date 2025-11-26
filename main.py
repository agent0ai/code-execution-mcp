#!/usr/bin/env python3
import os
import sys
from fastmcp import FastMCP
from code_execution_tool import CodeExecutionTool

# Initialize FastMCP server
mcp = FastMCP(
    "code-execution-mcp",
    instructions="Execute terminal commands and Python code on the host system using Agent Zero's battle-tested code execution tool."
)

# Get configuration from environment variables with defaults
EXECUTABLE = os.getenv("CODE_EXEC_EXECUTABLE", "/bin/bash")
INIT_COMMANDS_STR = os.getenv("CODE_EXEC_INIT_COMMANDS", "")
INIT_COMMANDS = [cmd.strip() for cmd in INIT_COMMANDS_STR.split(";") if cmd.strip()] if INIT_COMMANDS_STR else []

# Timeout configuration
FIRST_OUTPUT_TIMEOUT = int(os.getenv("CODE_EXEC_FIRST_OUTPUT_TIMEOUT", "30"))
BETWEEN_OUTPUT_TIMEOUT = int(os.getenv("CODE_EXEC_BETWEEN_OUTPUT_TIMEOUT", "15"))
DIALOG_TIMEOUT = int(os.getenv("CODE_EXEC_DIALOG_TIMEOUT", "5"))
MAX_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_MAX_EXEC_TIMEOUT", "180"))

# Create single CodeExecutionTool instance for state management
# This preserves Agent Zero's pattern of maintaining shell sessions across calls
code_tool = CodeExecutionTool(
    executable=EXECUTABLE,
    init_commands=INIT_COMMANDS,
    first_output_timeout=FIRST_OUTPUT_TIMEOUT,
    between_output_timeout=BETWEEN_OUTPUT_TIMEOUT,
    dialog_timeout=DIALOG_TIMEOUT,
    max_exec_timeout=MAX_EXEC_TIMEOUT
)


@mcp.tool()
async def execute_terminal(command: str, session: int = 0) -> str:
    try:
        result = await code_tool.execute_terminal_command(session=session, command=command)
        return result
    except Exception as e:
        return f"Error executing terminal command: {str(e)}"


@mcp.tool()
async def execute_python(code: str, session: int = 0) -> str:
    try:
        result = await code_tool.execute_python_code(session=session, code=code)
        return result
    except Exception as e:
        return f"Error executing Python code: {str(e)}"


@mcp.tool()
async def get_output(session: int = 0) -> str:
    try:
        result = await code_tool.get_terminal_output(session=session)
        return result
    except Exception as e:
        return f"Error getting terminal output: {str(e)}"


@mcp.tool()
async def reset_terminal(session: int = 0, reason: str | None = None) -> str:
    try:
        result = await code_tool.reset_terminal(session=session, reason=reason)
        return result
    except Exception as e:
        return f"Error resetting terminal: {str(e)}"


def main():
    # Run with stdio transport (default)
    mcp.run()


if __name__ == "__main__":
    main()
