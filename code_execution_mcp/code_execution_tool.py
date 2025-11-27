import asyncio
from dataclasses import dataclass
import shlex
import time
import re
import os
import sys
from .helpers.print_style import PrintStyle
from .helpers.shell_local import LocalInteractiveSession
from .helpers.strings import truncate_text as truncate_text_string
from .helpers.log import Log

def truncate_text_agent(output: str, threshold: int = 1000000) -> str:
    if len(output) <= threshold:
        return output
    return truncate_text_string(output, threshold)


@dataclass
class State:
    shells: dict[int, LocalInteractiveSession]


class CodeExecutionTool:

    def __init__(self, executable: str | None = None, init_commands: list[str] | None = None,
                 first_output_timeout: int = 30, between_output_timeout: int = 15,
                 dialog_timeout: int = 5, max_exec_timeout: int = 180):
        self.executable = executable
        self.init_commands = init_commands or []
        self.default_timeouts = {
            'first_output_timeout': first_output_timeout,
            'between_output_timeout': between_output_timeout,
            'dialog_timeout': dialog_timeout,
            'max_exec_timeout': max_exec_timeout,
        }
        self.state: State | None = None
        self.log = Log()  # Minimal log placeholder
        self.prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")

    def read_prompt(self, filename: str, **kwargs) -> str:
        filepath = os.path.join(self.prompts_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Simple template replacement
            for key, value in kwargs.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            return content
        except FileNotFoundError:
            return f"[Prompt file not found: {filename}]"

    async def prepare_state(self, reset=False, session: int | None = None):
        if not self.state:
            shells: dict[int, LocalInteractiveSession] = {}
        else:
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

        # initialize local interactive shell interface for session if needed
        if session is not None and session not in shells:
            shell = LocalInteractiveSession(executable=self.executable)
            shells[session] = shell
            await shell.connect()

            # Execute init commands if provided
            for cmd in self.init_commands:
                await shell.send_command(cmd)
                # Wait for init command to complete
                await asyncio.sleep(0.5)

        self.state = State(shells=shells)
        return self.state

    async def execute_python_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"{sys.executable} -m IPython -c {escaped_code}"
        prefix = "python> " + self.format_command_for_output(code) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def execute_terminal_command(self, session: int, command: str, reset: bool = False):
        prefix = "bash> " + self.format_command_for_output(command) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def terminal_session(self, session: int, command: str, reset: bool = False, prefix: str = ""):
        self.state = await self.prepare_state(reset=reset, session=session)

        # try again on lost connection
        for i in range(2):
            try:
                await self.state.shells[session].send_command(command)

                PrintStyle(
                    background_color="white", font_color="#1B4F72", bold=True
                ).print(f"Code execution output (local)")

                return await self.get_terminal_output(session=session, prefix=prefix)

            except Exception as e:
                if i == 0:  # try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True, session=session)
                    continue
                else:
                    raise e

    def format_command_for_output(self, command: str):
        # truncate long commands
        short_cmd = command[:200]
        # normalize whitespace for cleaner output
        short_cmd = " ".join(short_cmd.split())
        # final length
        short_cmd = truncate_text_string(short_cmd, 100)
        return f"{short_cmd}"

    async def get_terminal_output(
        self,
        session=0,
        reset_full_output=True,
        first_output_timeout=None,
        between_output_timeout=None,
        dialog_timeout=None,
        max_exec_timeout=None,
        sleep_time=0.1,
        prefix="",
    ):
        # Use default timeouts if not specified
        first_output_timeout = first_output_timeout or self.default_timeouts['first_output_timeout']
        between_output_timeout = between_output_timeout or self.default_timeouts['between_output_timeout']
        dialog_timeout = dialog_timeout or self.default_timeouts['dialog_timeout']
        max_exec_timeout = max_exec_timeout or self.default_timeouts['max_exec_timeout']

        self.state = await self.prepare_state(session=session)

        # Common shell prompt regex patterns (add more as needed)
        prompt_patterns = [
            re.compile(r"\(venv\).+[$#] ?$"),  # (venv) ...$ or (venv) ...#
            re.compile(r"root@[^:]+:[^#]+# ?$"),  # root@container:~#
            re.compile(r"[a-zA-Z0-9_.-]+@[^:]+:[^$#]+[$#] ?$"),  # user@host:~$
            re.compile(r"bash-\d+\.\d+\$ ?$"),  # bash-3.2$ (version can vary)
        ]

        # potential dialog detection
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

        # if prefix, log right away
        if prefix:
            self.log.log(type="code_exe", heading="Code Execution", content=prefix)

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
                got_output = True
                last_output_time = now

                # Check for shell prompt at the end of output
                last_lines = (
                    truncated_output.splitlines()[-3:] if truncated_output else []
                )
                last_lines.reverse()
                for idx, line in enumerate(last_lines):
                    for pat in prompt_patterns:
                        if pat.search(line.strip()):
                            PrintStyle.info(
                                "Detected shell prompt, returning output early."
                            )
                            return truncated_output

            # Check for max execution time
            if now - start_time > max_exec_timeout:
                sysinfo = self.read_prompt(
                    "fw.code.max_time.md", timeout=max_exec_timeout
                )
                response = self.read_prompt("fw.code.info.md", info=sysinfo)
                if truncated_output:
                    response = truncated_output + "\n\n" + response
                PrintStyle.warning(sysinfo)
                return response

            # Waiting for first output
            if not got_output:
                if now - start_time > first_output_timeout:
                    sysinfo = self.read_prompt(
                        "fw.code.no_out_time.md", timeout=first_output_timeout
                    )
                    response = self.read_prompt("fw.code.info.md", info=sysinfo)
                    PrintStyle.warning(sysinfo)
                    return response
            else:
                # Waiting for more output after first output
                if now - last_output_time > between_output_timeout:
                    sysinfo = self.read_prompt(
                        "fw.code.pause_time.md", timeout=between_output_timeout
                    )
                    response = self.read_prompt("fw.code.info.md", info=sysinfo)
                    if truncated_output:
                        response = truncated_output + "\n\n" + response
                    PrintStyle.warning(sysinfo)
                    return response

                # potential dialog detection
                if now - last_output_time > dialog_timeout:
                    # Check for dialog prompt at the end of output
                    last_lines = (
                        truncated_output.splitlines()[-2:] if truncated_output else []
                    )
                    for line in last_lines:
                        for pat in dialog_patterns:
                            if pat.search(line.strip()):
                                PrintStyle.info(
                                    "Detected dialog prompt, returning output early."
                                )

                                sysinfo = self.read_prompt(
                                    "fw.code.pause_dialog.md", timeout=dialog_timeout
                                )
                                response = self.read_prompt(
                                    "fw.code.info.md", info=sysinfo
                                )
                                if truncated_output:
                                    response = truncated_output + "\n\n" + response
                                PrintStyle.warning(sysinfo)
                                return response

    async def reset_terminal(self, session=0, reason: str | None = None):
        # Print the reason for the reset to the console if provided
        if reason:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}... Reason: {reason}"
            )
        else:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}..."
            )

        # Only reset the specified session while preserving others
        await self.prepare_state(reset=True, session=session)
        response = self.read_prompt(
            "fw.code.info.md", info=self.read_prompt("fw.code.reset.md")
        )
        return response

    def fix_full_output(self, output: str):
        # remove any single byte \xXX escapes
        output = re.sub(r"(?<!\\)\\x[0-9A-Fa-f]{2}", "", output)
        # Strip every line of output before truncation
        output = "\n".join(line.strip() for line in output.splitlines())
        output = truncate_text_agent(output=output, threshold=1000000)  # ~1MB
        return output
