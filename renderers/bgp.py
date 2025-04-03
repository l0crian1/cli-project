#!/usr/bin/env python3

import sys
import json

def check_for_deletions(deletions):
    """
    Check if any of the deletion paths affect the BGP configuration.
    
    Args:
        deletions: List of paths marked for deletion
        
    Returns:
        bool: True if any deletion path affects BGP, False otherwise
    """
    for path in deletions:
        # Check if this path starts with ['protocols', 'bgp']
        if len(path) >= 2 and path[0] == 'protocols' and path[1] == 'bgp':
            return True
        # Also check if the entire protocols section is being deleted
        if len(path) == 1 and path[0] == 'protocols':
            return True
    return False

if __name__ == "__main__":
    # Read and parse the configuration from stdin
    input_data = json.load(sys.stdin)
    
    # Check if we have the new format with deletions
    if isinstance(input_data, dict) and "config" in input_data and "deletions" in input_data:
        config = input_data["config"]
        deletions = input_data["deletions"]
        
        # Check if any deletions affect BGP
        has_bgp_deletions = check_for_deletions(deletions)
        
        if has_bgp_deletions:
            print("\nBGP section marked for deletion")
            # If the entire BGP section is being deleted, we should clear all BGP configuration
            # This will be handled by the empty config being passed to the BGP renderer
    else:
        # Legacy format, just use the input directly as the config
        config = input_data
        has_bgp_deletions = False
    
    print("\nBGP Configuration Received:")
    print(json.dumps(config.get("protocols", {}).get("bgp", {}), indent=2))
    
    # Check if we have any BGP configuration to apply or if we need to clear existing configuration
    bgp_config = config.get("protocols", {}).get("bgp", {})
    has_bgp_config = bool(bgp_config)
    
    # Only apply changes if we have BGP config to apply or if we're deleting BGP config
    if has_bgp_config or has_bgp_deletions:
        # Here you would generate and apply the BGP configuration
        # For now, we'll just print a message
        print("\nBGP configuration would be applied here")
    else:
        print("\nNo BGP configuration to apply or clear")