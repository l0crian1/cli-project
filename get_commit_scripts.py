import json

def get_scripts_to_run(candidate_config, running_config=None):
    """
    Determine which scripts need to be run based on the candidate configuration.
    Dynamically finds scripts by looking for the 'script' field in the config.json structure.
    Also includes scripts for sections that are marked for deletion.
    
    Args:
        candidate_config: The candidate configuration dictionary
        running_config: The running configuration dictionary (optional)
        
    Returns:
        list: List of script names to run
    """
    scripts = []
    
    # Load the main config to get script mappings
    with open('config.json', 'r') as f:
        main_config = json.load(f)
    
    # Find all paths in the candidate config
    def get_candidate_paths(config, current_path=None):
        if current_path is None:
            current_path = []
            
        paths = []
        
        if isinstance(config, dict):
            for key, value in config.items():
                new_path = current_path + [key]
                paths.append(new_path)
                if isinstance(value, dict):
                    paths.extend(get_candidate_paths(value, new_path))
        
        return paths
    
    # Find all paths in the main config that have a script field
    def find_script_paths(config, current_path=None):
        if current_path is None:
            current_path = []
            
        script_paths = []
        
        if isinstance(config, dict):
            if 'script' in config:
                script_paths.append(current_path)
            
            for key, value in config.items():
                if isinstance(value, dict):
                    script_paths.extend(find_script_paths(value, current_path + [key]))
        
        return script_paths
    
    # Get all paths in the candidate config
    candidate_paths = get_candidate_paths(candidate_config)
    
    # Get all paths in the main config that have a script field
    script_paths = find_script_paths(main_config)
    
    # For each script path, check if any candidate path starts with it
    for script_path in script_paths:
        for candidate_path in candidate_paths:
            if len(candidate_path) >= len(script_path) and candidate_path[:len(script_path)] == script_path:
                # Get the script from the main config
                current = main_config
                for part in script_path:
                    current = current[part]
                
                if 'script' in current and current['script'] not in scripts:
                    scripts.append(current['script'])
                break
    
    # Also check for paths that are marked for deletion
    def find_deletion_paths(config, current_path=None):
        if current_path is None:
            current_path = []
            
        deletion_paths = []
        
        if isinstance(config, dict):
            for key, value in config.items():
                if value is None:  # This is a deletion marker
                    deletion_paths.append(current_path + [key])
                elif isinstance(value, dict):
                    deletion_paths.extend(find_deletion_paths(value, current_path + [key]))
        
        return deletion_paths
    
    # Get all paths marked for deletion
    deletion_paths = find_deletion_paths(candidate_config)
    
    # For each script path, check if any deletion path starts with it or is a parent of it
    for script_path in script_paths:
        for deletion_path in deletion_paths:
            # Check if deletion path starts with script path (direct deletion)
            if len(deletion_path) >= len(script_path) and deletion_path[:len(script_path)] == script_path:
                # Get the script from the main config
                current = main_config
                for part in script_path:
                    current = current[part]
                
                if 'script' in current and current['script'] not in scripts:
                    scripts.append(current['script'])
                break
            
            # Check if script path starts with deletion path (parent deletion)
            if len(script_path) >= len(deletion_path) and script_path[:len(deletion_path)] == deletion_path:
                # Check if this protocol had configuration in the running config
                if running_config is not None:
                    # Check if the protocol had configuration in the running config
                    has_config = False
                    current = running_config
                    for part in script_path:
                        if part in current:
                            current = current[part]
                        else:
                            current = None
                            break
                    
                    if current is not None and current:
                        has_config = True
                    
                    # Only add the script if the protocol had configuration
                    if has_config:
                        # Get the script from the main config
                        current = main_config
                        for part in script_path:
                            current = current[part]
                        
                        if 'script' in current and current['script'] not in scripts:
                            scripts.append(current['script'])
                else:
                    # If no running config is provided, add the script
                    current = main_config
                    for part in script_path:
                        current = current[part]
                    
                    if 'script' in current and current['script'] not in scripts:
                        scripts.append(current['script'])
                break
    
    return scripts

if __name__ == '__main__':
    # Example usage
    with open('router-config.json', 'r') as f:
        candidate = json.load(f)
    
    scripts = get_scripts_to_run(candidate)
    print("Scripts to run:", scripts) 