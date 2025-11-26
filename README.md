# Code Execution MCP Server

A Model Context Protocol (MCP) server that exposes [Agent Zero's](https://github.com/agent0ai/agent-zero) battle-tested code execution capabilities.

This MCP server allows any AI agent (Claude, GPT-4, etc.) to execute terminal commands and Python code on the host system using Agent Zero's proven implementation.

## Features

- **Execute Terminal Commands**: Run shell commands with full session persistence
- **Execute Python Code**: Run Python code via IPython with session management
- **Multiple Sessions**: Maintain separate execution contexts
- **Smart Output Handling**: Automatic prompt detection, timeout management, and dialog detection
- **Cross-Platform**: Works on Linux, macOS, and Windows (experimental)

## Installation

```bash
# Clone or download this package
cd code-execution-mcp

# Install dependencies
pip install -e .

# For Windows support
pip install -e ".[windows]"
```

## Configuration

The MCP server can be configured via environment variables:

```bash
# Shell executable (default: /bin/bash on Unix, cmd.exe on Windows)
export CODE_EXEC_EXECUTABLE=/bin/bash

# Init commands (semicolon-separated, run when creating new sessions)
export CODE_EXEC_INIT_COMMANDS="source /path/to/venv/bin/activate;export PATH=\$PATH:/custom/bin"

# Timeout configuration (in seconds)
export CODE_EXEC_FIRST_OUTPUT_TIMEOUT=30      # Wait for first output
export CODE_EXEC_BETWEEN_OUTPUT_TIMEOUT=15    # Wait between output chunks
export CODE_EXEC_DIALOG_TIMEOUT=5             # Detect dialog prompts
export CODE_EXEC_MAX_EXEC_TIMEOUT=180         # Maximum execution time
```

## MCP Client Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "code-execution": {
      "command": "python",
      "args": ["/Users/lazy/Projects/A0-code-tool-MCP/code-execution-mcp/main.py"],
      "env": {
        "CODE_EXEC_EXECUTABLE": "/bin/bash",
        "CODE_EXEC_INIT_COMMANDS": "source /Users/lazy/Projects/A0-code-tool-MCP/code-execution-mcp/.venv/bin/activate"
      }
    }
  }
}
```

## Available Tools

### execute_terminal
Execute a terminal command in the specified session.

**Parameters:**
- `command` (string, required): The shell command to execute
- `session` (integer, optional): Session number (default: 0)

**Example:**
```python
await execute_terminal(command="ls -la", session=0)
```

### execute_python
Execute Python code via IPython in the specified session.

**Parameters:**
- `code` (string, required): The Python code to execute
- `session` (integer, optional): Session number (default: 0)

**Example:**
```python
await execute_python(code="import sys; print(sys.version)", session=0)
```

### get_output
Get accumulated output from a terminal session.

**Parameters:**
- `session` (integer, optional): Session number (default: 0)

**Example:**
```python
await get_output(session=0)
```

### reset_terminal
Reset a terminal session, closing and reopening it.

**Parameters:**
- `session` (integer, optional): Session number (default: 0)
- `reason` (string, optional): Reason for the reset

**Example:**
```python
await reset_terminal(session=0, reason="Environment corrupted")
```

## Session Management

Sessions allow maintaining separate execution contexts:

- Session 0: Default session for general commands
- Session 1+: Additional sessions for isolated environments

Each session maintains:
- Shell state (environment variables, working directory)
- Command history
- Output buffer

## Virtual Environment Considerations

**Important:** When the MCP server is launched from a virtual environment, shell sessions may NOT automatically inherit the venv activation.

**Solution:** Use init commands to explicitly activate your virtual environment:

```json
{
  "env": {
    "CODE_EXEC_INIT_COMMANDS": "source /path/to/venv/bin/activate"
  }
}
```

## Platform Support

- **Linux**: Fully tested and supported
- **macOS**: Fully tested and supported
- **Windows**: Experimental support via pywinpty
  - Install with: `pip install -e ".[windows]"`
  - Use `cmd.exe` or `powershell.exe` as executable
  - Some features may behave differently

## Architecture

This MCP server is a **minimal wrapper** around Agent Zero's code execution tool:

- Preserves Agent Zero's battle-tested logic
- No rewrites or reimplementations
- Uses Agent Zero's helper modules unchanged:
  - `tty_session.py` - TTY session management
  - `shell_local.py` - Local shell interface
  - `print_style.py` - Output styling and logging
  - `strings.py` - String manipulation utilities

## Security

**WARNING:** This MCP server allows full code execution on the host system. Security is the responsibility of the MCP client.

Only use with trusted AI agents and in controlled environments.

## License

MIT License

This project wraps and reuses code from [Agent Zero](https://github.com/agent0ai/agent-zero) (Copyright (c) 2025 Agent Zero, s.r.o), which is licensed under the MIT License.

See the LICENSE file for full license text and attribution details.

## Credits

**Built on Agent Zero's proven code execution implementation.**

This MCP server preserves and reuses Agent Zero's battle-tested code:
- Core execution logic from `code_execution_tool.py`
- Helper modules: `tty_session.py`, `shell_local.py`, `print_style.py`, `strings.py`
- All system message prompts

All credit for the robust code execution implementation goes to the [Agent Zero](https://github.com/agent0ai/agent-zero) team.

Uses [FastMCP](https://gofastmcp.com/) for MCP protocol handling.
