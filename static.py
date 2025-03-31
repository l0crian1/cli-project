#!/usr/bin/env python3

from typing import Dict, List, Tuple, Any, Optional, Union
from jinja2 import Environment, FileSystemLoader, Template
import os
import subprocess
import logging

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
    logger.info("Extracting static routes from configuration")
    static = config.get("protocols", {}).get("static", {}).get("route", {})
    routes: List[Tuple[str, str, Optional[str]]] = []

    for prefix, data in static.items():
        logger.debug(f"Processing route prefix: {prefix}")
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
                        logger.warning(f"Error processing distance for route {prefix} - {str(e)}")
            
            routes.append((prefix, nh, distance_value))
            logger.info(f"Added route: {prefix} via {nh}" + (f" distance {distance_value}" if distance_value else ""))

    logger.info(f"Extracted {len(routes)} static routes")
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
    logger.info("Generating FRR configuration for static routes")
    routes = extract_static_routes(config_dict)
    
    template_dir = os.path.dirname(os.path.abspath(__file__))
    logger.debug(f"Using template directory: {template_dir}")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    try:
        template = env.get_template("frr.conf.j2")
        config = template.render(static_routes=routes)
        logger.info("Successfully generated FRR configuration")
        logger.debug(f"Generated configuration:\n{config}")
        return config
    except Exception as e:
        logger.error(f"Error generating FRR configuration: {str(e)}")
        return ""  # Return empty string on error

def apply_config(config_dict: Dict[str, Any]) -> bool:
    """
    Apply static routes configuration to the system.
    
    Args:
        config_dict: Configuration dictionary containing static routes
        
    Returns:
        bool: True if configuration was applied successfully, False otherwise
    """
    logger.info("Applying static routes configuration")
    try:
        # Generate FRR configuration
        frr_config = generate_static_routes_config(config_dict)
        if not frr_config:
            logger.error("No static routes configuration generated")
            return False

        # Write configuration to temporary file
        temp_file = "/tmp/frr_static_routes.conf"
        logger.debug(f"Writing configuration to temporary file: {temp_file}")
        with open(temp_file, "w") as f:
            f.write(frr_config)

        # Apply configuration using vtysh
        logger.info("Applying configuration using vtysh")
        result = subprocess.run(
            ["vtysh", "-f", temp_file],
            capture_output=True,
            text=True,
            check=True
        )

        # Clean up temporary file
        os.remove(temp_file)
        logger.debug("Removed temporary configuration file")

        if result.returncode == 0:
            logger.info("Static routes configuration applied successfully")
            return True
        else:
            logger.error(f"Error applying static routes configuration: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing vtysh command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error applying static routes configuration: {str(e)}")
        return False

def validate_config(config_dict: Dict[str, Any]) -> bool:
    """
    Validate the static routes configuration.
    
    Args:
        config_dict: Configuration dictionary containing static routes
        
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    logger.info("Validating static routes configuration")
    try:
        routes = extract_static_routes(config_dict)
        if not routes:
            logger.warning("No static routes found in configuration")
            return False

        for prefix, next_hop, distance in routes:
            # Basic validation of prefix format
            if '/' not in prefix:
                logger.error(f"Invalid prefix format: {prefix}")
                return False

            # Basic validation of next-hop format
            if not next_hop or next_hop.count('.') != 3:
                logger.error(f"Invalid next-hop format: {next_hop}")
                return False

            # Validate distance if present
            if distance and not distance.isdigit():
                logger.error(f"Invalid distance value: {distance}")
                return False

        logger.info("Static routes configuration validation successful")
        return True

    except Exception as e:
        logger.error(f"Error validating static routes configuration: {str(e)}")
        return False
