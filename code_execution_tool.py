"""Stripped code execution tool for MCP - based on Agent Zero's implementation."""
import asyncio
from dataclasses import dataclass
import time
import re
import os
from helpers.print_style import PrintStyle
from helpers.shell_local import LocalInteractiveSession
from helpers.strings import truncate_text
from helpers.log import Log

@dataclass
class State:
    """State container for code execution tool."""
    shells: dict[int, LocalInteractiveSession]
    executable: str
    init_commands: list[str]

class CodeExecutionTool:
    """Code execution tool for terminal and Python execution."""

    def __init__(self, executable: str = "/bin/bash", init_commands: list[str] = None, options: dict = None):
        self.executable = executable
        self.init_commands = init_commands or []
        self.options = options or {}
        self.state: State | None = None
        self.log = Log()  # Placeholder log
        self._python_sessions = set()  # Track which sessions have Python running

        # Timeout defaults from options
        self.first_output_timeout = self.options.get("first_output_timeout", 30)
        self.between_output_timeout = self.options.get("between_output_timeout", 15)
        self.dialog_timeout = self.options.get("dialog_timeout", 5)
        self.max_exec_timeout = self.options.get("max_exec_timeout", 180)

    def read_prompt(self, filename: str, **kwargs) -> str:
        """Read prompt file and replace template variables."""
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
        try:
            with open(prompt_path, "r") as f:
                content = f.read()
            # Replace template variables
            for key, value in kwargs.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            return content
        except FileNotFoundError:
            return f"[Prompt file {filename} not found]"

    async def prepare_state(self, reset: bool = False, session: int | None = None):
        """Initialize or reset shell state."""
        if not self.state:
            self.state = State(shells={}, executable=self.executable, init_commands=self.init_commands)

        shells = self.state.shells.copy()

        # Only reset the specified session if provided
        if reset and session is not None and session in shells:
            await shells[session].close()
            del shells[session]
        elif reset and session is None:
            # Close all sessions if full reset requested
            for s in list(shells.keys()):
                await shells[s].close()
            shells = {}

        # Initialize shell for session if needed
        if session is not None and session not in shells:
            shell = LocalInteractiveSession(executable=self.executable)
            shells[session] = shell
            await shell.connect()

            # Execute init commands
            for cmd in self.init_commands:
                await shell.send_command(cmd)
                await shell.read_output(timeout=2)

        self.state = State(shells=shells, executable=self.executable, init_commands=self.init_commands)
        return self.state

    async def execute_python_code(self, session: int, code: str, reset: bool = False):
        """Execute Python code in persistent Python REPL."""
        self.state = await self.prepare_state(reset=reset, session=session)

        # Start Python REPL if not already running in this session
        if session not in self._python_sessions:
            await self.state.shells[session].send_command("python3 -i")
            await asyncio.sleep(0.3)  # Give Python time to start
            # Clear the startup output
            await self.state.shells[session].read_output(timeout=1, reset_full_output=True)
            self._python_sessions.add(session)

        # Send the Python code to the running REPL
        prefix = "python> " + self.format_command_for_output(code) + "\n\n"
        await self.state.shells[session].send_command(code)

        # Get output without resetting the buffer
        return await self.get_terminal_output(
            session=session,
            prefix=prefix,
            reset_full_output=False
        )

    async def execute_terminal_command(self, session: int, command: str, reset: bool = False):
        """Execute terminal command, automatically exiting Python mode if needed."""
        self.state = await self.prepare_state(reset=reset, session=session)

        # If session is in Python mode, exit Python first
        if session in self._python_sessions:
            PrintStyle(font_color="#FFA500").print(
                f"Session {session} is in Python mode. Exiting Python to run shell command..."
            )
            await self.state.shells[session].send_command("exit()")
            await asyncio.sleep(0.2)  # Wait for Python to exit
            await self.state.shells[session].read_output(timeout=1, reset_full_output=True)
            self._python_sessions.discard(session)

        prefix = "bash> " + self.format_command_for_output(command) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def terminal_session(self, session: int, command: str, reset: bool = False, prefix: str = ""):
        """Execute command in terminal session."""
        self.state = await self.prepare_state(reset=reset, session=session)

        # Try twice on lost connection
        for i in range(2):
            try:
                await self.state.shells[session].send_command(command)

                PrintStyle(background_color="white", font_color="#1B4F72", bold=True).print(
                    f"Code execution output (local)"
                )
                return await self.get_terminal_output(session=session, prefix=prefix)

            except Exception as e:
                if i == 0:
                    # Try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True, session=session)
                    continue
                else:
                    raise e

    def format_command_for_output(self, command: str):
        """Format command for display in output."""
        # Truncate long commands
        short_cmd = command[:200]
        # Normalize whitespace for cleaner output
        short_cmd = " ".join(short_cmd.split())
        # Final length
        short_cmd = truncate_text(short_cmd, 100)
        return f"{short_cmd}"

    async def get_terminal_output(
        self,
        session: int = 0,
        reset_full_output: bool = True,
        first_output_timeout: int | None = None,
        between_output_timeout: int | None = None,
        dialog_timeout: int | None = None,
        max_exec_timeout: int | None = None,
        sleep_time: float = 0.1,
        prefix: str = "",
    ):
        """Get terminal output with timeout handling."""
        # Use provided timeouts or defaults
        first_output_timeout = first_output_timeout or self.first_output_timeout
        between_output_timeout = between_output_timeout or self.between_output_timeout
        dialog_timeout = dialog_timeout or self.dialog_timeout
        max_exec_timeout = max_exec_timeout or self.max_exec_timeout

        self.state = await self.prepare_state(session=session)

        # Common shell prompt regex patterns
        prompt_patterns = [
            re.compile(r"\(venv\).+[$#] ?$"),  # (venv) ...$ or (venv) ...#
            re.compile(r"root@[^:]+:[^#]+# ?$"),  # root@container:~#
            re.compile(r"[a-zA-Z0-9_.-]+@[^:]+:[^$#]+[$#] ?$"),  # user@host:~$
            re.compile(r"bash-\d+\.\d+\$ ?$"),  # bash-3.2$ (version can vary)
        ]

        # Potential dialog detection
        dialog_patterns = [
            re.compile(r"Y/N", re.IGNORECASE),  # Y/N anywhere in line
            re.compile(r"yes/no", re.IGNORECASE),  # yes/no anywhere in line
            re.compile(r":\s*$"),  # line ending with colon
            re.compile(r"\?\s*$"),  # line ending with question mark
        ]

        start_time = time.time()
        last_output_time = start_time
        full_output = ""
        truncated_output = ""
        got_output = False

        while True:
            await asyncio.sleep(sleep_time)
            full_output, partial_output = await self.state.shells[session].read_output(
                timeout=1, reset_full_output=reset_full_output
            )
            reset_full_output = False  # only reset once

            now = time.time()
            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                truncated_output = self.fix_full_output(full_output)
                self.log.update(content=prefix + truncated_output)
                last_output_time = now
                got_output = True

                # Check for shell prompt at the end of output
                last_lines = truncated_output.splitlines()[-3:] if truncated_output else []
                last_lines.reverse()
                for idx, line in enumerate(last_lines):
                    for pat in prompt_patterns:
                        if pat.search(line.strip()):
                            PrintStyle.info("Detected shell prompt, returning output early.")
                            return truncated_output

            # Check for max execution time
            if now - start_time > max_exec_timeout:
                sysinfo = self.read_prompt("fw.code.max_time.md", timeout=max_exec_timeout)
                response = self.read_prompt("fw.code.info.md", info=sysinfo)
                if truncated_output:
                    response = truncated_output + "\n\n" + response
                PrintStyle.warning(sysinfo)
                self.log.update(content=prefix + response)
                return response

            # Waiting for first output
            if not got_output:
                if now - start_time > first_output_timeout:
                    sysinfo = self.read_prompt("fw.code.no_out_time.md", timeout=first_output_timeout)
                    response = self.read_prompt("fw.code.info.md", info=sysinfo)
                    PrintStyle.warning(sysinfo)
                    self.log.update(content=prefix + response)
                    return response
            else:
                # Waiting for more output after first output
                if now - last_output_time > between_output_timeout:
                    sysinfo = self.read_prompt("fw.code.pause_time.md", timeout=between_output_timeout)
                    response = self.read_prompt("fw.code.info.md", info=sysinfo)
                    if truncated_output:
                        response = truncated_output + "\n\n" + response
                    PrintStyle.warning(sysinfo)
                    self.log.update(content=prefix + response)
                    return response

                # Potential dialog detection
                if now - last_output_time > dialog_timeout:
                    # Check for dialog prompt at the end of output
                    last_lines = truncated_output.splitlines()[-2:] if truncated_output else []
                    for line in last_lines:
                        for pat in dialog_patterns:
                            if pat.search(line.strip()):
                                PrintStyle.info("Detected dialog prompt, returning output early.")

                                sysinfo = self.read_prompt("fw.code.pause_dialog.md", timeout=dialog_timeout)
                                response = self.read_prompt("fw.code.info.md", info=sysinfo)
                                if truncated_output:
                                    response = truncated_output + "\n\n" + response
                                PrintStyle.warning(sysinfo)
                                self.log.update(content=prefix + response)
                                return response

    async def reset_terminal(self, session: int = 0, reason: str | None = None):
        """Reset a terminal session."""
        if reason:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}... Reason: {reason}"
            )
        else:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}..."
            )

        # Clear Python session tracking for this session
        self._python_sessions.discard(session)

        # Only reset the specified session while preserving others
        await self.prepare_state(reset=True, session=session)
        response = self.read_prompt("fw.code.info.md", info=self.read_prompt("fw.code.reset.md"))
        self.log.update(content=response)
        return response

    def fix_full_output(self, output: str):
        """Clean and truncate output."""
        # Remove any single byte \xXX escapes
        output = re.sub(r"(?<!\\)\\x[0-9A-Fa-f]{2}", "", output)
        # Strip every line of output before truncation
        output = "\n".join(line.strip() for line in output.splitlines())
        # Truncate to ~1MB - larger outputs should be dumped to file
        output = truncate_text(output, 1000000)
        return output
