#!/usr/bin/env python3

import ipaddress
import subprocess
import json
from typing import List, Callable, Dict, Any, Optional

def validate_ip_address(value: str) -> bool:
    """Validate if a string is a valid IP address."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def validate_ip_prefix(value: str) -> bool:
    """Validate if a string is a valid IP prefix (CIDR notation)."""
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False

def validate_ip_address_or_prefix(value: str) -> bool:
    """Validate if a string is either a valid IP address or prefix."""
    return validate_ip_address(value) or validate_ip_prefix(value)

def validate_vrf_name(value: str) -> bool:
    """Validate if a string is a valid VRF name."""
    if value == "all":
        return True

    try:
        result = subprocess.run(
            ["ip", "-j", "vrf", "show"],
            capture_output=True,
            text=True,
            check=True
        )
        vrf_list = json.loads(result.stdout)
        valid_names = [vrf.get("name") for vrf in vrf_list if "name" in vrf]
        return value in valid_names
    except subprocess.SubprocessError:
        print("Warning: Could not check VRF name - 'ip' command failed")
        return True  # Allow the name if we can't verify
    except json.JSONDecodeError:
        print("Warning: Could not parse VRF list - invalid JSON format")
        return True  # Allow the name if we can't verify
    except Exception as e:
        print(f"Warning: VRF name validation failed - {str(e)}")
        return True  # Allow the name if we can't verify
    
def is_num_1_65535(value: str) -> bool:
    """Validate if a string represents a number between 1 and 65535."""
    try:
        val = int(value)
        return 1 <= val <= 65535
    except ValueError:
        return False
    
def is_num_1_255(value: str) -> bool:
    """Validate if a string represents a number between 1 and 255."""
    try:
        val = int(value)
        return 1 <= val <= 255
    except ValueError:
        return False
    
def is_valid_enum(value: str, allowed: List[str]) -> bool:
    """Validate if a value is in a list of allowed values."""
    return value in allowed

def make_enum_validator(allowed_values: List[str]) -> Callable[[str], bool]:
    """Create a validator function for enum values."""
    return lambda value: is_valid_enum(value, allowed_values)

# Dictionary mapping validator names to their functions
validators: Dict[str, Callable[[str], bool]] = {
    "ip-address": validate_ip_address,
    "ip-prefix": validate_ip_prefix,
    "ip-address-or-prefix": validate_ip_address_or_prefix,
    "vrf-name": validate_vrf_name,
    "num-1-65535": is_num_1_65535,
    "num-1-255": is_num_1_255,
    "enum": None  # This is handled specially in the command validator
}
