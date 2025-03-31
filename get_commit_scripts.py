import json

def get_scripts_to_run(candidate_config):
    """
    Determine which scripts need to be run based on the candidate configuration.
    Only includes scripts for protocols that have configuration in the candidate config.
    
    Args:
        candidate_config: The candidate configuration dictionary
        
    Returns:
        list: List of script names to run
    """
    scripts = []
    
    # Get the protocols section from candidate config
    protocols = candidate_config.get('protocols', {})
    
    # Load the main config to get script mappings
    with open('config.json', 'r') as f:
        main_config = json.load(f)
    
    # For each protocol in the candidate config
    for protocol in protocols:
        # If this protocol exists in main config and has a script field
        if protocol in main_config.get('protocols', {}) and 'script' in main_config['protocols'][protocol]:
            # Only add the script if there's actual configuration for this protocol
            if protocols[protocol]:  # Check if the protocol has any configuration
                scripts.append(main_config['protocols'][protocol]['script'])
    
    return scripts

if __name__ == '__main__':
    # Example usage
    with open('router-config.json', 'r') as f:
        candidate = json.load(f)
    
    scripts = get_scripts_to_run(candidate)
    print("Scripts to run:", scripts) 