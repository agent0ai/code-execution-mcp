# Code Execution MCP Server

A standalone MCP (Model Context Protocol) server that exposes Agent Zero's battle-tested code execution capabilities to any AI agent. Execute terminal commands and Python code on your host system via stdio transport.

## Features

- **Terminal Execution**: Run shell commands in persistent sessions
- **Python Execution**: Execute Python code via IPython
- **Multiple Sessions**: Support for independent numbered sessions (0, 1, 2, etc.)
- **Session Management**: Reset sessions when needed
- **Configurable Timeouts**: Fine-tune execution timeouts
- **Init Commands**: Run setup commands when sessions start
- **Clean Output**: Automatically removes ANSI codes for LLM consumption

## Installation

### From Source

```bash
git clone <repository-url>
cd code_exec_mcp
pip install -e .
```

### Optional: Windows Support

For Windows users, install the Windows-specific dependencies:

```bash
pip install -e ".[windows]"
```

## Configuration

### MCP Client Configuration

Add to your MCP client configuration file (e.g., Claude Desktop config):

```json
{
  "mcpServers": {
    "code-execution": {
      "command": "python",
      "args": ["/path/to/code_exec_mcp/main.py"],
      "env": {
        "EXECUTABLE": "/bin/bash",
        "INIT_COMMANDS": "source /path/to/venv/bin/activate",
        "FIRST_OUTPUT_TIMEOUT": "30",
        "BETWEEN_OUTPUT_TIMEOUT": "15",
        "DIALOG_TIMEOUT": "5",
        "MAX_EXEC_TIMEOUT": "180"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXECUTABLE` | `/bin/bash` | Shell executable to use (`/bin/bash`, `cmd.exe`, etc.) |
| `INIT_COMMANDS` | `""` | Semicolon-separated commands to run on session start |
| `FIRST_OUTPUT_TIMEOUT` | `30` | Seconds to wait for first output |
| `BETWEEN_OUTPUT_TIMEOUT` | `15` | Seconds to wait between outputs |
| `DIALOG_TIMEOUT` | `5` | Seconds before detecting dialog prompts |
| `MAX_EXEC_TIMEOUT` | `180` | Maximum execution time in seconds |

### Virtual Environment Setup

**IMPORTANT**: If your MCP server needs to run in a virtual environment, use `INIT_COMMANDS` to activate it:

```json
"env": {
  "INIT_COMMANDS": "source /home/user/myproject/venv/bin/activate; cd /home/user/myproject"
}
```

Multiple commands can be chained with semicolons.

## Available Tools

### 1. execute_terminal

Execute a terminal command in the specified session.

```json
{
  "name": "execute_terminal",
  "arguments": {
    "command": "ls -la",
    "session": 0
  }
}
```

### 2. execute_python

Execute Python code via IPython in the specified session.

```json
{
  "name": "execute_python",
  "arguments": {
    "code": "import sys; print(sys.version)",
    "session": 0
  }
}
```

### 3. get_output

Get accumulated output from a terminal session.

```json
{
  "name": "get_output",
  "arguments": {
    "session": 0
  }
}
```

### 4. reset_terminal

Reset a terminal session (close and reopen).

```json
{
  "name": "reset_terminal",
  "arguments": {
    "session": 0
  }
}
```

## Usage Examples

### Execute a Simple Command

```python
# Agent requests
execute_terminal(command="echo 'Hello World'", session=0)
# Returns: Hello World
```

### Execute Python Code

```python
# Agent requests
execute_python(code="x = 5 + 3; print(x)", session=0)
# Returns: python> x = 5 + 3; print(x)
#          8
```

### Multiple Sessions

```python
# Start long-running process in session 1
execute_terminal(command="npm run dev", session=1)

# Work in session 0 while session 1 runs
execute_terminal(command="git status", session=0)

# Check output from session 1
get_output(session=1)
```

### Reset a Stuck Session

```python
# Session became unresponsive
reset_terminal(session=0)
# Returns: [Terminal session 0 has been reset]
```

## How It Works

### Session Management

- Each session number (0, 1, 2, etc.) maintains an independent shell
- Sessions persist across tool calls until reset
- Init commands execute automatically when a new session is created
- Sessions are isolated from each other

### Session Modes and State Management

Sessions can operate in two modes:

#### Shell Mode (Default)
- Sessions start in shell mode, running your configured shell (bash, zsh, etc.)
- Use `execute_terminal` to run shell commands
- Shell environment variables and working directory persist across commands

#### Python Mode (Persistent REPL)
- Activated automatically when you first call `execute_python` on a session
- Starts a persistent Python REPL (`python3 -i`)
- Python variables, imports, and state persist across multiple `execute_python` calls
- **Automatic Mode Switching**: When you call `execute_terminal` on a Python-mode session, the system automatically:
  1. Exits the Python REPL
  2. Returns to shell mode
  3. Executes your shell command
  4. **Note**: This clears all Python state (variables, imports, etc.)

#### Best Practices for Session Usage

**Strategy 1: Single Session with Automatic Switching (Simple)**
```python
# Python work
execute_python("x = [1, 2, 3]", session=0)
execute_python("x.append(4)", session=0)  # x persists

# Switch to shell (Python state is lost)
execute_terminal("ls -la", session=0)  # Automatically exits Python

# Back to Python (fresh state)
execute_python("y = 5", session=0)  # x is no longer defined
```

**Strategy 2: Dedicated Sessions (Recommended for Complex Work)**
```python
# Session 0: Shell commands only
execute_terminal("git status", session=0)
execute_terminal("npm run build", session=0)

# Session 1: Python work only
execute_python("import pandas as pd", session=1)
execute_python("df = pd.read_csv('data.csv')", session=1)
execute_python("df.head()", session=1)  # All Python state persists

# Session 2: Long-running process
execute_terminal("npm run dev", session=2)
```

**Strategy 3: Explicit Reset When Needed**
```python
# Python work
execute_python("data = [1, 2, 3]", session=0)

# Explicitly reset to start fresh
reset_terminal(session=0)

# Now in clean shell state
execute_terminal("echo 'Clean slate'", session=0)
```

### Output Handling

The server automatically:
- Detects shell prompts and returns output early
- Detects dialog prompts (Y/N questions) and returns for user input
- Removes ANSI escape codes for clean LLM consumption
- Truncates very large outputs (~1MB limit)
- Handles various timeout scenarios gracefully

### Timeout Behavior

1. **First Output Timeout**: If no output appears within this time, returns timeout message
2. **Between Output Timeout**: If output pauses for this duration, assumes completion
3. **Dialog Timeout**: Detects prompts (Y/N, yes/no, colons, questions) after this delay
4. **Max Execution Timeout**: Hard cap on total execution time

## Platform Support

### Linux / macOS

Fully supported with default `/bin/bash` executable.

### Windows

Experimental support via `pywinpty`. Set executable to `cmd.exe`:

```json
"env": {
  "EXECUTABLE": "cmd.exe"
}
```

Install Windows dependencies:
```bash
pip install -e ".[windows]"
```

## Security Considerations

**WARNING**: This MCP server allows ANY connected agent to execute arbitrary code on your host system.

- Only use with trusted AI agents
- Only use in controlled environments
- Consider running in a container or VM
- MCP client should handle authentication/authorization
- Review all code before execution in production environments

## Troubleshooting

### Common Errors and Solutions

#### 1. "bash: !": event not found"

**Cause**: Exclamation marks (`!`) trigger bash history expansion.

**Solutions**:
```python
# ❌ Don't use ! in double-quoted strings
execute_terminal('echo "Hello!"', session=0)

# ✅ Remove the exclamation mark
execute_terminal('echo "Hello"', session=0)

# ✅ Or use single quotes
execute_terminal("echo 'Hello!'", session=0)

# ✅ Or escape it
execute_terminal('echo "Hello\\!"', session=0)
```

#### 2. "ModuleNotFoundError: No module named 'X'"

**Cause**: Python package not installed in the environment.

**Solutions**:
```python
# Option 1: Install in the session
execute_terminal("pip install numpy pandas matplotlib", session=0)
execute_python("import numpy as np", session=0)

# Option 2: Use virtual environment with packages via INIT_COMMANDS
# In your MCP config:
"INIT_COMMANDS": "source /path/to/venv/bin/activate"

# Option 3: Use only standard library
execute_python("import math, random, json", session=0)  # These work everywhere
```

#### 3. "SyntaxError: invalid syntax" (Shell Commands in Python Mode)

**Cause**: Session was in Python mode, and shell commands were sent to Python interpreter.

**Old Behavior** (Pre-fix): Required manual reset
```python
execute_python("x = 5", session=0)  # Enters Python mode
execute_terminal("ls", session=0)   # ❌ SyntaxError
reset_terminal(session=0)           # Manual reset required
execute_terminal("ls", session=0)   # ✅ Now works
```

**New Behavior** (Automatic): Mode switching happens automatically
```python
execute_python("x = 5", session=0)     # Enters Python mode
execute_terminal("ls", session=0)      # ✅ Automatically exits Python and runs command
execute_python("y = 10", session=0)    # Fresh Python session (x is undefined)
```

**Best Practice**: Use dedicated sessions to avoid mode switching
```python
execute_terminal("ls", session=0)      # Session 0 for shell
execute_python("x = 5", session=1)     # Session 1 for Python
execute_python("x + 10", session=1)    # x still defined
execute_terminal("pwd", session=0)     # No mode switching needed
```

### Virtual Environment Not Active

If Python packages aren't found, the virtual environment may not be active. Use `INIT_COMMANDS`:

```json
"INIT_COMMANDS": "source /path/to/venv/bin/activate"
```

### Session Hangs or Becomes Unresponsive

Use `reset_terminal` to close and restart the session:

```python
reset_terminal(session=0)
```

### Timeouts Too Short/Long

Adjust timeout environment variables based on your use case:

```json
"FIRST_OUTPUT_TIMEOUT": "60",     # Longer for slow commands
"BETWEEN_OUTPUT_TIMEOUT": "5",    # Shorter for fast output
"MAX_EXEC_TIMEOUT": "300"         # 5 minutes max
```

### Python State Not Persisting

**Issue**: Variables defined in one `execute_python` call are undefined in the next.

**Causes and Solutions**:

1. **Automatic mode switching cleared Python state**
   ```python
   execute_python("x = 5", session=0)
   execute_terminal("ls", session=0)     # Exits Python, clears state
   execute_python("print(x)", session=0) # ❌ NameError: x not defined
   ```
   **Solution**: Use dedicated sessions
   ```python
   execute_python("x = 5", session=1)
   execute_terminal("ls", session=0)     # Different session
   execute_python("print(x)", session=1) # ✅ x is still defined
   ```

2. **Session was reset**
   ```python
   execute_python("x = 5", session=0)
   reset_terminal(session=0)             # Clears all state
   execute_python("print(x)", session=0) # ❌ NameError
   ```

### Accumulated Output Not Showing

**Issue**: `get_output()` returns timeout message instead of previous command output.

**Cause**: Fixed in recent versions. Ensure you're using the latest code.

**Workaround**: Command output is included in the response from `execute_terminal` and `execute_python`, so you typically don't need `get_output` unless checking on long-running commands.

## Architecture

This MCP server is built on Agent Zero's proven code execution infrastructure:

- **tty_session.py**: Cross-platform PTY/TTY session management
- **shell_local.py**: Local interactive shell interface
- **code_execution_tool.py**: Core execution logic with timeout handling
- **Prompt files**: System messages for various scenarios

All Agent Zero code is preserved with minimal modifications for MCP compatibility.

## Development

### Project Structure

```
code_exec_mcp/
├── main.py                    # MCP server entry point
├── code_execution_tool.py     # Core execution logic
├── helpers/
│   ├── tty_session.py        # PTY/TTY management
│   ├── shell_local.py        # Shell interface
│   ├── clean_string.py       # Output cleaning
│   ├── print_style.py        # Console styling
│   ├── strings.py            # String utilities
│   └── log.py                # Logging placeholder
├── prompts/                   # System message templates
└── pyproject.toml            # Package definition
```

### Running Tests

```bash
# Test terminal execution
python -c "import asyncio; from code_execution_tool import CodeExecutionTool; asyncio.run(CodeExecutionTool().execute_terminal_command(0, 'echo test'))"

# Test Python execution
python -c "import asyncio; from code_execution_tool import CodeExecutionTool; asyncio.run(CodeExecutionTool().execute_python_code(0, 'print(42)'))"
```

## License

MIT License - Based on Agent Zero's code execution infrastructure

## Credits

Built on [Agent Zero](https://github.com/agent0ai/agent-zero)'s battle-tested code execution tool.
