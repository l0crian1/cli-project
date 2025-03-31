#!/usr/bin/env python3
import json
import subprocess
import os
import socket
from tabulate import tabulate

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application.run_in_terminal import run_in_terminal
from prompt_toolkit.document import Document
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.history import FileHistory


from validators import validators
from suggestors import suggestors

from cli_common import AutoSuggestFromTree, TreeCompleter, CommandValidator, print_possible_completions
from cli_common import setup_keybindings

import configCli


with open("op.json") as f:
    commands_json = json.load(f)


def find_command(path, root):
    node = root
    tag_values = {}

    for part in path:
        if part in node:
            node = node[part]
        else:
            tag_key = next((k for k, v in node.items()
                            if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if tag_key:
                tag_values[tag_key] = part
                node = node[tag_key]
            else:
                break

    if isinstance(node, dict) and "command" in node:
        cmd = node["command"]
        for tag, val in tag_values.items():
            cmd = cmd.replace(tag, val)
        return cmd

    return None

def execute_command(cmd):
    import os
    expanded_cmd = os.path.expandvars(cmd)

    parts = expanded_cmd.split()
    if parts[0].endswith(".py"):
        parts.insert(0, "python3")
        subprocess.run(parts)
    else:
        subprocess.run(expanded_cmd, shell=True)

def main():
    bindings = setup_keybindings(commands_json, print_possible_completions, suggestors)

    completer = TreeCompleter(commands_json)
    session = PromptSession(
        completer=completer,
        key_bindings=bindings,
        complete_while_typing=False,
        auto_suggest=AutoSuggestFromTree(commands_json),
        history=FileHistory(os.path.expanduser("~/.cli_history"))
    )


    print("Entering operational mode (type 'exit' to quit, use '?' to list options)\n")
    restore_text = None

    while True:
        try:
            prompt_str = f"{os.getlogin()}@{socket.gethostname()}:~$ "
            raw_input = session.prompt(prompt_str, default=restore_text or "")
            if not raw_input.strip():
                continue

            for user_input in raw_input.strip().splitlines():
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input == "configure":
                    configCli.main()
                    continue  # skip further processing of this line


                if user_input == "exit":
                    raise EOFError()

                restore_text = None
                parts = user_input.split()

                try:
                    CommandValidator(commands_json).validate(Document(user_input))
                except ValidationError as ve:
                    print(f"\n{ve.message}\n")
                    node = commands_json
                    rollback_index = 0
                    for i, part in enumerate(parts):
                        if part in node:
                            node = node[part]
                            rollback_index = i + 1
                        else:
                            tag_entry = next(((k, v) for k, v in node.items()
                                            if isinstance(v, dict) and v.get("type") == "tagNode"), None)
                            if tag_entry:
                                node = tag_entry[1]
                                rollback_index = i
                            else:
                                break
                    restore_text = " ".join(parts[:rollback_index]) + " "
                    continue

                command = find_command(parts, commands_json)
                if command:
                    print(f"\nExecuting: {command}\n")
                    execute_command(command)
                else:
                    print("\nUnknown or incomplete command\n")

        except KeyboardInterrupt:
            restore_text = None
            session.default_buffer.reset(Document())
            session.app.invalidate()
            continue
        except EOFError:
            break

if __name__ == "__main__":
    main()
