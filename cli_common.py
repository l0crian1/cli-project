#!/usr/bin/env python3

# cli_common.py
import os
from typing import Dict, List, Optional, Any, Iterator, Tuple, Callable
    
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application.run_in_terminal import run_in_terminal
from prompt_toolkit.document import Document
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError

from tabulate import tabulate

from validators import validators
from suggestors import suggestors

class AutoSuggestFromTree(AutoSuggest):
    """Provides auto-suggestions based on a command tree structure."""
    
    def __init__(self, root: Dict[str, Any]):
        self.root = root

    def get_suggestion(self, buffer: Any, document: Document) -> Optional[Suggestion]:
        """Get suggestion for current input."""
        parts = document.text.strip().split()
        node = self.root

        if not parts:
            return None

        *base_parts, last_part = parts
        for part in base_parts:
            node = node.get(part) or next((v for k, v in node.items()
                                           if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if not node:
                return None

        # Only suggest static (non-tagNode) keys
        candidates = [k for k in node
                      if isinstance(node[k], dict) and node[k].get("type") != "tagNode" and k.startswith(last_part)]

        if not candidates:
            return None

        common_prefix = os.path.commonprefix(candidates)

        if common_prefix and common_prefix != last_part:
            return Suggestion(common_prefix[len(last_part):])

        return None

class TreeCompleter(Completer):
    """Provides command completion based on a tree structure."""
    
    def __init__(self, tree: Dict[str, Any]):
        self.tree = tree

    def get_completions(self, document: Document, complete_event: Any) -> Iterator[Completion]:
        """Get completions for current input."""
        text = document.text_before_cursor
        parts = text.strip().split()
        node = self.tree

        is_mid_token = not text.endswith(" ")
        path_parts = parts[:-1] if is_mid_token else parts
        last_word = parts[-1] if is_mid_token else ""

        if not parts:
            yield from self._get_base_completions(node)
            return

        for part in path_parts:
            node = node.get(part) or next((v for k, v in node.items()
                                           if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if not node:
                return

        if isinstance(node, dict):
            yield from self._get_node_completions(node, last_word)

    def _get_base_completions(self, node: Dict[str, Any]) -> Iterator[Completion]:
        """Get completions for base level commands."""
        for key, val in node.items():
            if isinstance(val, dict) and val.get("type") != "tagNode":
                yield Completion(text=key, start_position=0)

    def _get_node_completions(self, node: Dict[str, Any], last_word: str) -> Iterator[Completion]:
        """Get completions for a specific node in the tree."""
        for key, val in node.items():
            if not isinstance(val, dict):
                continue

            if val.get("type") == "tagNode" and "suggestor" in val:
                sugg_name = val["suggestor"]
                if sugg_name in suggestors:
                    args = val.get("suggestor_args", [])
                    try:
                        for option in suggestors[sugg_name](*args):
                            if option.startswith(last_word):
                                yield Completion(text=option, start_position=-len(last_word))
                    except Exception as e:
                        yield Completion(text=f"<error: {sugg_name}>", start_position=0)
            elif val.get("type") != "tagNode" and key.startswith(last_word):
                yield Completion(text=key, start_position=-len(last_word))

class CommandValidator(Validator):
    """Validates commands against a command tree structure."""
    
    def __init__(self, root: Dict[str, Any]):
        self.root = root

    def validate(self, document: Document) -> None:
        """Validate the command against the command tree."""
        parts = document.text.strip().split()
        node = self.root

        for part in parts:
            if part in node:
                node = node[part]
            else:
                tag_entry = next(((k, v) for k, v in node.items()
                                  if isinstance(v, dict) and v.get("type") == "tagNode"), None)
                if tag_entry:
                    tag_node = tag_entry[1]
                    validator_type = tag_node.get("validator")
                    if validator_type:
                        if validator_type == "enum":
                            allowed = tag_node.get("enum-values", [])
                            validator_fn = lambda v: v in allowed
                        else:
                            validator_fn = validators.get(validator_type)

                        if validator_fn and not validator_fn(part):
                            raise ValidationError(
                                message=f"'{part}' is not a valid {validator_type.replace('-', ' ')}.",
                                cursor_position=document.text.find(part)
                            )

                    node = tag_node
                else:
                    break

def print_possible_completions(path: List[str], root: Dict[str, Any]) -> None:
    """Print possible completions for the current command path."""
    node = root

    for part in path:
        if part in node:
            node = node[part]
        else:
            tag_entry = next((v for k, v in node.items()
                              if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if tag_entry:
                node = tag_entry
            else:
                print("No completions found.\n")
                return

    if not isinstance(node, dict):
        print("No completions found.\n")
        return

    rows = [["<enter>", "Execute the current command"]] if "command" in node else []
    rows.extend(_get_completion_rows(node))

    if not rows:
        print("No completions found.\n")
        return

    print("\nPossible completions:\n")
    print("  " + tabulate(rows, tablefmt="plain").replace("\n", "\n  "))

def _get_completion_rows(node: Dict[str, Any]) -> List[List[str]]:
    """Get completion rows for a node."""
    rows = []
    for k, v in node.items():
        if not isinstance(v, dict):
            continue

        desc = v.get("description", "")
        node_type = v.get("type")

        if node_type == "tagNode":
            rows.append([k, desc])
            if "suggestor" in v:
                rows.extend(_get_suggestor_rows(v))
        else:
            rows.append([k, desc])
    return rows

def _get_suggestor_rows(node: Dict[str, Any]) -> List[List[str]]:
    """Get completion rows from a suggestor."""
    print(f"DEBUG: _get_suggestor_rows called with node={node}")  # Debug print
    rows = []
    sugg_name = node["suggestor"]
    args = node.get("suggestor_args", [])
    print(f"DEBUG: Calling suggestor {sugg_name} with args={args}")  # Debug print
    if sugg_name in suggestors:
        try:
            suggestions = suggestors[sugg_name](*args)
            print(f"DEBUG: Got suggestions: {suggestions}")  # Debug print
            rows.extend([[s, ""] for s in suggestions])
        except Exception as e:
            print(f"DEBUG: Error calling suggestor: {e}")  # Debug print
            rows.append([f"<error calling {sugg_name}>", str(e)])
    else:
        print(f"DEBUG: Suggestor {sugg_name} not found")  # Debug print
        rows.append([f"<missing suggestor: {sugg_name}>", ""])
    return rows

def setup_keybindings(commands_json: Dict[str, Any], 
                     print_possible_completions: Callable[[List[str], Dict[str, Any]], None],
                     suggestors: Dict[str, Callable]) -> KeyBindings:
    """Set up key bindings for the CLI."""
    bindings = KeyBindings()

    @bindings.add('?', eager=True)
    def show_possible(event):
        buffer = event.app.current_buffer
        text = buffer.text.strip()
        parts = text.split()
        run_in_terminal(lambda: print_possible_completions(parts if parts else [], commands_json))
        buffer.insert_text("")

    @bindings.add('tab')
    def autocomplete(event):
        buffer = event.app.current_buffer
        text = buffer.text
        document = Document(text=text, cursor_position=len(text))

        parts = text.strip().split()
        if not parts:
            return

        is_mid_token = not text.endswith(" ")
        last_token = parts[-1] if is_mid_token else ""
        last_token_len = len(last_token)

        # Traverse to node
        node = commands_json
        for part in parts[:-1] if is_mid_token else parts:
            node = node.get(part) or next((v for k, v in node.items()
                                           if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if not node:
                return

        rows = _get_completion_rows(node)

        if "command" in node:
            rows.insert(0, ["<enter>", "Execute the current command"])

        if not rows:
            return

        plain_matches = [r[0] for r in rows if not r[0].startswith('<') and r[0].startswith(last_token)]

        if plain_matches:
            common_prefix = os.path.commonprefix(plain_matches)
            if len(plain_matches) == 1:
                # If there's only one valid match, complete and add a space
                if is_mid_token:
                    buffer.delete_before_cursor(last_token_len)
                buffer.insert_text(plain_matches[0] + " ")
                return
            elif common_prefix and common_prefix != last_token:
                # If there's a common prefix longer than current token, complete it
                if is_mid_token:
                    buffer.delete_before_cursor(last_token_len)
                buffer.insert_text(common_prefix)
                return

        # If no direct completion possible, show all possibilities
        run_in_terminal(lambda: print_possible_completions(parts if parts else [], commands_json))

    return bindings
    

                