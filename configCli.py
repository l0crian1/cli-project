#!/usr/bin/env python3
import json
import subprocess
import os
import socket
from typing import Dict, List, Optional, Tuple, Any
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

from jinja2 import Environment, FileSystemLoader
from get_commit_scripts import get_scripts_to_run

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_SAVE_PATH = os.path.join(SCRIPT_DIR, "router-config.json")

class ConfigError(Exception):
    """Base class for configuration related errors."""
    pass

class PathNotFoundError(ConfigError):
    """Raised when a configuration path is not found."""
    pass

def load_saved_config() -> Dict:
    """Load the saved configuration from disk."""
    if os.path.exists(CONFIG_SAVE_PATH):
        try:
            with open(CONFIG_SAVE_PATH) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error loading configuration: Invalid JSON format - {e}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
    return {}

def save_current_config(config_dict: Dict) -> None:
    """Save the current configuration to disk."""
    try:
        with open(CONFIG_SAVE_PATH, "w") as f:
            json.dump(config_dict, f, indent=2)
        print(f"Configuration saved to {CONFIG_SAVE_PATH}")
    except Exception as e:
        print(f"Failed to save configuration: {e}")

def load_commands_json() -> Dict:
    """Load command structure and configuration schema."""
    try:
        # Load the command structure
        with open("commands.json") as f:
            commands = json.load(f)
        
        # Load the configuration schema
        with open("config.json") as f:
            config_schema = json.load(f)
        
        # Add the config schema to set and delete commands
        commands["set"].update(config_schema)
        commands["delete"].update(config_schema)
        
        return commands
    except FileNotFoundError as e:
        print(f"Error: Required JSON file not found - {e.filename}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in configuration files - {e}")
        raise
    except Exception as e:
        print(f"Error loading configuration files: {e}")
        raise

def get_nested_value(d: Dict, path_parts: List[str]) -> Optional[Any]:
    """Get a nested value from a dictionary using a path list."""
    current = d
    for part in path_parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current

def key_exists_in_config(config_dict: Dict, path_dict: Dict) -> bool:
    """Check if a path exists in the config dictionary."""
    def extract_path(d: Dict) -> List[str]:
        path = []
        while isinstance(d, dict) and d:
            key = next(iter(d))
            path.append(key)
            d = d[key]
        return path

    path = extract_path(path_dict)
    return get_nested_value(config_dict, path) is not None

def parse_config_command(command: str, root: Dict) -> Tuple[Dict, str]:
    parts = command.split()
    action = parts[0]  # 'set', 'delete', or 'show'
    path_parts = parts[1:]
    config_dict = {}
    current = config_dict
    node = root

    # Build the configuration dictionary
    for i, part in enumerate(path_parts):
        # Validate against schema
        if part in node:
            node = node[part]
        else:
            tag_entry = next(((k, v) for k, v in node.items()
                              if isinstance(v, dict) and v.get("type") == "tagNode"), None)
            if tag_entry:
                tag_node = tag_entry[1]
                validator_type = tag_node.get("validator")
                if validator_type in validators and not validators[validator_type](part):
                    raise ValidationError(
                        message=f"'{part}' is not a valid {validator_type.replace('-', ' ')}.",
                        cursor_position=command.find(part)
                    )
                node = tag_node

        # If this is the last part or the next part is a value
        if i == len(path_parts) - 1:
            current[part] = {}
        else:
            # Create nested dictionary
            if part not in current:
                current[part] = {}
            current = current[part]

    return config_dict, action

def update_config_dict(existing_dict, new_dict, schema_node=None, path=None, value_to_delete=False):
    """Update an existing configuration dictionary with new values."""
    path = path or []
    
    for key, value in new_dict.items():
        current_path = path + [key]
        
        # Handle deletion
        if value is None or value_to_delete:
            if key in existing_dict:
                del existing_dict[key]
            continue

        # Create/update the key in the existing dictionary
        if isinstance(value, dict):
            if key not in existing_dict:
                existing_dict[key] = {}
            if value:  # If value is not an empty dict
                update_config_dict(existing_dict[key], value, schema_node, current_path)
            # Don't delete empty dicts as they represent valid leaf nodes
        else:
            existing_dict[key] = value

def delete_from_config_dict(config_dict, delete_dict):
    def extract_path(d):
        path = []
        while isinstance(d, dict) and d:
            key = next(iter(d))
            path.append(key)
            d = d[key]
        return path

    def _delete_path(current, keys):
        if not keys:
            print("\nError: Cannot delete – no path specified\n")
            return False
            
        *parents, last_key = keys
        for key in parents:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]

        if isinstance(current, dict) and last_key in current:
            del current[last_key]
            # Clean up empty parent dictionaries
            return True
        return False

    key_path = extract_path(delete_dict)
    return _delete_path(config_dict, key_path)

def populate_config_tree(config, show_tree, include_candidate=False, candidate_config=None, schema=None):
    """
    Populate the command tree with configuration paths.
    If include_candidate is True, also include paths from the candidate configuration.
    """
    def merge_trees(tree1, tree2):
        for key, value in tree2.items():
            if key not in tree1:
                tree1[key] = value
            elif isinstance(tree1[key], dict) and isinstance(value, dict):
                merge_trees(tree1[key], value)

    def get_schema_node(key, current_schema):
        if not current_schema:
            return None
        # First check if this is a direct child
        if key in current_schema:
            return current_schema[key]
        # Then check if we have a tagNode that would match
        for k, v in current_schema.items():
            if isinstance(v, dict) and v.get("type") == "tagNode":
                return v
        return None

    # First populate with running config
    for key, value in config.items():

        # Get the schema node for this key
        schema_node = get_schema_node(key, schema)

        # If this key is under a tagNode or is a configured value, don't add a description
        if schema_node and schema_node.get("type") == "tagNode":
            #print(json.dumps(schema_node.get("description"),indent=4))
            show_tree[key] = {"type": "tagNode"}
        else:
            show_tree[key] = {"description": schema_node.get("description", "")}
        if isinstance(value, dict):
            populate_config_tree(value, show_tree[key], schema=schema_node)

    # If requested, merge in candidate config paths
    if include_candidate and candidate_config:
        temp_tree = {}
        for key, value in candidate_config.items():
            if value is not None:  # Skip deleted paths

                # Get the schema node for this key
                schema_node = get_schema_node(key, schema)

                # If this key is under a tagNode or is a configured value, don't add a description
                if schema_node and schema_node.get("type") == "tagNode":
                    temp_tree[key] = {"type": "tagNode"}
                else:
                    temp_tree[key] = {"description": schema_node.get("description", "")}
                if isinstance(value, dict):
                    populate_config_tree(value, temp_tree[key], schema=schema_node)
        merge_trees(show_tree, temp_tree)


def dict_to_set_commands(config_dict, current_path=None, show_deletions=False):
    if current_path is None:
        current_path = []
    
    commands = []
    for key, value in config_dict.items():
        path = current_path + [key]
        if value is None and show_deletions:
            # This is a deletion marker
            commands.append(f"delete {' '.join(path)}")
        elif isinstance(value, dict):
            if not value:  # Empty dict means it's a leaf node
                commands.append(f"set {' '.join(path)}")
            else:
                commands.extend(dict_to_set_commands(value, path, show_deletions))
    return commands

def show_subtree(parts, running_config, candidate_config):
    print("\nShowing Configuration:\n")
    
    if len(parts) >= 2:
        if parts[1] == "commands":
            show_type = parts[2] if len(parts) > 2 else "candidate"
            if show_type == "running":
                commands = dict_to_set_commands(running_config)
                print("Running configuration:")
            elif show_type == "candidate":
                commands = dict_to_set_commands(candidate_config, show_deletions=True)
                print("Candidate configuration (uncommitted changes):")
            else:
                print(f"Invalid show command: {' '.join(parts)}")
                return
                
            if commands:
                print("\n".join(commands))
            else:
                print("No configuration commands found.")
            return
        
        elif parts[1] == "running":
            print("Running configuration (raw format):")
            print(json.dumps(running_config, indent=2))
            return
        elif parts[1] == "candidate":
            print("Candidate configuration (raw format):")
            print(json.dumps(candidate_config, indent=2))
            return
    
    # For bare 'show' command or 'show <path>'
    if len(parts) == 1:  # Just 'show'
        if candidate_config:  # If candidate config is not empty
            print("Candidate configuration (uncommitted changes):")
            print(json.dumps(candidate_config, indent=2))
        else:  # If candidate config is empty
            print("Running configuration:")
            print(json.dumps(running_config, indent=2))
        return
        
    # For 'show <path>', use merged config
    merged_config = running_config.copy()
    update_config_dict(merged_config, candidate_config)
    node = merged_config
    
    for part in parts[1:]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            print(f"No configuration found for: {' '.join(parts[1:])}")
            return
    print(json.dumps(node, indent=2))

def handle_commit(running_config, candidate_config):
    try:
        # Get list of scripts that need to be run
        scripts_to_run = get_scripts_to_run(candidate_config)
        print("\nScripts that will be run:", scripts_to_run)
        
        # Generate config using the merged running and candidate configs
        merged_config = running_config.copy()
        
        def get_full_path(d, current_path=None):
            if current_path is None:
                current_path = []
            paths = []
            for key, value in d.items():
                path = current_path + [key]
                if value is None:
                    paths.append(path)
                elif isinstance(value, dict):
                    paths.extend(get_full_path(value, path))
            return paths

        # Get all paths marked for deletion
        paths_to_delete = get_full_path(candidate_config)
        
        # Delete specific paths from merged config
        def delete_path(config, path):
            if not path:
                return
            current = config
            *parents, last = path
            
            # Navigate to parent of the node to delete
            for key in parents:
                if key not in current or not isinstance(current[key], dict):
                    return
                current = current[key]
            
            # Delete the node
            if last in current:
                del current[last]
                
            # Clean up empty parent dictionaries
            if not current:
                parent = config
                for key in parents[:-1]:
                    if not parent[key]:
                        del parent[key]
                    parent = parent[key]

        # Process deletions first
        for path in paths_to_delete:
            delete_path(merged_config, path)

        # Process additions (excluding paths marked for deletion)
        def process_additions(target_dict, source_dict):
            for key, value in source_dict.items():
                if value is None:
                    continue  # Skip deletion markers
                elif isinstance(value, dict):
                    if key not in target_dict:
                        target_dict[key] = {}
                    if value:  # Only recurse if there are more levels
                        process_additions(target_dict[key], value)
                    elif not target_dict[key]:  # Empty dict means leaf node
                        target_dict[key] = {}

        # Add/modify remaining items from candidate config
        process_additions(merged_config, candidate_config)

        # Run each script with the merged configuration
        for script in scripts_to_run:
            script_path = script  # Use the script path as-is from config.json
            try:
                process = subprocess.run(
                    ['python3', script_path],
                    input=json.dumps(merged_config),
                    text=True,
                    capture_output=True,
                    check=True
                )
                if process.stdout:
                    print(f"\nOutput from {script}:")
                    print(process.stdout)
            except subprocess.CalledProcessError as e:
                print(f"\nError running {script}:")
                print(e.stderr)
                raise Exception(f"Script {script} failed with return code {e.returncode}")
        
        # Update running config with candidate changes
        running_config.clear()
        running_config.update(merged_config)
        candidate_config.clear()  # Clear candidate config after successful commit
        
        print("\nCommit successful - Configuration changes have been applied")
    except Exception as e:
        print(f"Error during commit:\n{e}")

def handle_delete_command(running_config, candidate_config, parsed_command, parts):
    # First, check if the path exists in the candidate config
    if key_exists_in_config(candidate_config, parsed_command):
        # If it exists in candidate, delete it from there
        delete_from_config_dict(candidate_config, parsed_command)
        return
    
    # If not in candidate, check if it exists in running config
    if key_exists_in_config(running_config, parsed_command):
        # If it exists in running, mark it for deletion in candidate by preserving the path
        def mark_for_deletion(config_dict, path_dict):
            for key, value in path_dict.items():
                if isinstance(value, dict) and value:  # Only recurse if there are more levels
                    if key not in config_dict:
                        config_dict[key] = {}
                    mark_for_deletion(config_dict[key], value)
                else:
                    config_dict[key] = None

        mark_for_deletion(candidate_config, parsed_command)
        return
    
    # If path doesn't exist in either config
    print(f"\nError: Cannot delete – path {' '.join(parts[1:])} does not exist in either configuration\n")

def compare_configs(running_config, candidate_config, as_commands=False):
    """Compare running and candidate configurations and show the differences."""
    print("\nConfiguration Differences:\n")

    if not candidate_config:
        print("No changes to commit (candidate configuration is empty)")
        return

    def get_all_paths(config, prefix=None):
        if prefix is None:
            prefix = []
        paths = {}
        for key, value in config.items():
            current_path = prefix + [key]
            path_str = " ".join(current_path)
            if value is None:
                paths[path_str] = None
            elif isinstance(value, dict):
                if not value:  # Empty dict means leaf node
                    paths[path_str] = {}
                else:
                    paths.update(get_all_paths(value, current_path))
        return paths

    def get_nested_value(d, path_parts):
        current = d
        for part in path_parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    running_paths = get_all_paths(running_config)
    candidate_paths = get_all_paths(candidate_config)

    if as_commands:
        # Show differences as commands
        added = []
        deleted = []
        
        # Find additions and modifications
        for path, value in candidate_paths.items():
            path_parts = path.split()
            if value is None:
                # Check if the path exists in running config before marking as deletion
                if get_nested_value(running_config, path_parts) is not None:
                    deleted.append(f"- delete {path}")
            elif path not in running_paths:
                added.append(f"+ set {path}")

        if added or deleted:
            if deleted:
                print("Changes that will be deleted:")
                for line in deleted:
                    print(line)
            if deleted and added:
                print()
            if added:
                print("Changes that will be added:")
                for line in added:
                    print(line)
        else:
            print("No changes found")
    else:
        # Show raw configuration differences
        def format_dict(d, indent=0):
            lines = []
            for k, v in d.items():
                if v is None:
                    lines.append(f"{'  ' * indent}- {k}")  # Just show the key being deleted
                elif isinstance(v, dict):
                    if not v:  # Empty dict means leaf node
                        lines.append(f"{'  ' * indent}+ {k}")
                    else:
                        lines.append(f"{'  ' * indent}{k}:")
                        lines.extend(format_dict(v, indent + 1))
            return lines

        print("Candidate configuration changes:")
        formatted = format_dict(candidate_config)
        if formatted:
            print("\n".join(formatted))
        else:
            print("No changes found")

def handle_compare_command(parts, running_config, candidate_config):
    """Handle the compare command and its variants."""
    if len(parts) > 1 and parts[1] == "commands":
        compare_configs(running_config, candidate_config, as_commands=True)
    else:
        compare_configs(running_config, candidate_config, as_commands=False)

def create_prompt_session(commands_json):
    bindings = setup_keybindings(commands_json, print_possible_completions, suggestors)
    completer = TreeCompleter(commands_json)

    return PromptSession(
        completer=completer,
        key_bindings=bindings,
        complete_while_typing=False,
        auto_suggest=AutoSuggestFromTree(commands_json),
        history=FileHistory(os.path.expanduser("~/.cfg_history"))
    )

def main():
    commands_json = load_commands_json()
    session = create_prompt_session(commands_json)
    running_config = load_saved_config()  # Load the saved/running config
    candidate_config = {}  # Initialize empty candidate config
    
    # Initialize command trees with running config only
    populate_config_tree(running_config, commands_json["show"], schema=commands_json["set"])  # Use set schema for show
    populate_config_tree(running_config, commands_json["delete"], include_candidate=True, 
                        candidate_config=candidate_config, schema=commands_json["set"])  # Use set schema for delete

    print("Entering configuration mode (type 'exit' to quit, use '?' to list options)\n")
    restore_text = None

    while True:
        try:
            prompt_str = f"{os.getlogin()}@{socket.gethostname()}# "
            raw_input = session.prompt(prompt_str, default=restore_text or "")
            if not raw_input.strip():
                continue

            for user_input in raw_input.strip().splitlines():
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input == "exit":
                    raise EOFError()
                if user_input == "commit":
                    handle_commit(running_config, candidate_config)
                    # After commit, update command trees with new running config
                    populate_config_tree(running_config, commands_json["show"], schema=commands_json["set"])
                    populate_config_tree(running_config, commands_json["delete"], include_candidate=True, 
                                      candidate_config=candidate_config, schema=commands_json["set"])
                    continue
                if user_input == "save":
                    save_current_config(running_config)
                    continue
                if user_input == "discard":
                    candidate_config.clear()  # Clear all candidate changes
                    print("\nDiscarded all uncommitted changes")
                    # Update command trees after discarding changes
                    populate_config_tree(running_config, commands_json["show"], schema=commands_json["set"])
                    populate_config_tree(running_config, commands_json["delete"], include_candidate=True, 
                                      candidate_config=candidate_config, schema=commands_json["set"])
                    continue

                restore_text = None
                parts = user_input.split()

                try:
                    CommandValidator(commands_json).validate(Document(user_input))
                    if parts[0] == "compare":
                        handle_compare_command(parts, running_config, candidate_config)
                        continue

                    parsed_command, action = parse_config_command(user_input, commands_json)

                    if action == "set":
                        update_config_dict(candidate_config, parsed_command, commands_json)
                        # Update command trees to include new candidate config
                        populate_config_tree(running_config, commands_json["show"], schema=commands_json["set"])
                        populate_config_tree(running_config, commands_json["delete"], include_candidate=True, 
                                          candidate_config=candidate_config, schema=commands_json["set"])
                    elif action == "delete":
                        handle_delete_command(running_config, candidate_config, parsed_command, parts)
                        # Update command trees after deletion
                        populate_config_tree(running_config, commands_json["show"], schema=commands_json["set"])
                        populate_config_tree(running_config, commands_json["delete"], include_candidate=True, 
                                          candidate_config=candidate_config, schema=commands_json["set"])
                    elif action == "show":
                        show_subtree(parts, running_config, candidate_config)

                except ValidationError as ve:
                    print(f"\n{ve.message}\n")
                    restore_text = ""  # Reset to empty prompt instead of restoring to last keyword
                    continue

        except KeyboardInterrupt:
            restore_text = None
            session.default_buffer.reset(Document())
            session.app.invalidate()
            continue
        except EOFError:
            break

if __name__ == "__main__":
    main()
    
