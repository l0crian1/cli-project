#!/usr/bin/env python3

from typing import Dict, List, Tuple, Any, Optional, Union
from jinja2 import Environment, FileSystemLoader, Template
import os
import sys
import json
import logging
import tempfile
import subprocess

def extract_static_routes(config: Dict[str, Any]) -> List[Tuple[str, str, Optional[str]]]:
    """
    Extract static routes from the configuration dictionary.
    
    Args:
        config: Configuration dictionary containing protocols and static routes
        
    Returns:
        List of tuples containing (prefix, next-hop, distance)
        
    Example:
        >>> config = {
        ...     "protocols": {
        ...         "static": {
        ...             "route": {
        ...                 "192.168.1.0/24": {
        ...                     "next-hop": {
        ...                         "10.0.0.1": {"distance": {"1": None}}
        ...                     }
        ...                 }
        ...             }
        ...         }
        ...     }
        ... }
        >>> extract_static_routes(config)
        [('192.168.1.0/24', '10.0.0.1', '1')]
    """
    static = config.get("protocols", {}).get("static", {}).get("route", {})
    routes: List[Tuple[str, str, Optional[str]]] = []

    for prefix, data in static.items():
        next_hops = data.get("next-hop", {})
        for nh, nh_data in next_hops.items():
            distance_value = None
            
            if isinstance(nh_data, dict):
                distance = nh_data.get("distance")
                if isinstance(distance, dict):
                    # Pick the first (and should be only) distance value
                    try:
                        distance_value = next(iter(distance))
                    except StopIteration:
                        # Empty distance dictionary, keep distance_value as None
                        pass
                    except Exception as e:
                        print(f"Warning: Error processing distance for route {prefix} - {str(e)}")
            
            routes.append((prefix, nh, distance_value))

    return routes

def generate_static_routes_config(config_dict: Dict[str, Any]) -> str:
    """
    Generate FRR configuration for static routes.
    
    Args:
        config_dict: Configuration dictionary containing static routes
        
    Returns:
        String containing the rendered FRR configuration
        
    Raises:
        FileNotFoundError: If the template file is not found
        jinja2.exceptions.TemplateNotFound: If the template cannot be loaded
    """
    routes = extract_static_routes(config_dict)
    
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    try:
        template = env.get_template("frr.conf.j2")
        return template.render(static_routes=routes)
    except Exception as e:
        print(f"Error generating FRR configuration: {str(e)}")
        return ""  # Return empty string on error

def apply_config(config_str: str) -> bool:
    """
    Apply the generated configuration using frr-reload.
    
    Args:
        config_str: The configuration string to apply
        
    Returns:
        bool: True if configuration was applied successfully, False otherwise
    """
    if not config_str:
        print("No configuration to apply")
        return False

    try:
        # Create a temporary file to store the configuration
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(config_str)
            temp_path = temp_file.name

        try:
            # Apply the configuration using frr-reload
            result = subprocess.run(
                ['frr-reload', '--reload', temp_path],
                capture_output=True,
                text=True,
                check=True
            )
            print("Configuration applied successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Error applying configuration: {e.stderr}")
            return False

        finally:
            # Clean up the temporary file
            os.unlink(temp_path)

    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    # Read and parse the configuration from stdin
    config = json.load(sys.stdin)
    print("\nStatic Route Configuration Received:")
    print(json.dumps(config, indent=2))
    
    # Generate the configuration
    config_str = generate_static_routes_config(config)
    
    # Apply the configuration
    if not apply_config(config_str):
        sys.exit(1)  # Exit with error if configuration failed
