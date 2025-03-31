#!/usr/bin/env python3

import os
from typing import List, Optional, Union

def list_interfaces(prefixes: Optional[Union[List[str], str]] = None) -> List[str]:
    """
    List network interfaces, filtered by prefixes.
    
    Args:
        prefixes: Optional list of prefixes or single prefix to filter interfaces by.
                 If None, uses default interface filter list.
        
    Returns:
        List of interface names sorted alphabetically
    """
    interface_filter = [
        'eth', 'bond', 'br', 'dum', 'gnv', 'ifb', 'l2tpeth', 'lo', 'macsec', 'peth',
        'pppoe', 'sstpc', 'tun', 'veth', 'vti', 'vtun', 'vxlan', 'wlan', 'wg',
        'wwan', 'zt'
    ]
    
    if prefixes is None:
        prefixes = interface_filter
    elif isinstance(prefixes, str):
        prefixes = [prefixes]
        
    try:
        net_dir = "/sys/class/net"
        
        if not os.path.exists(net_dir):
            print(f"Warning: Network interface directory {net_dir} not found")
            return []
            
        interfaces = os.listdir(net_dir)
        return sorted([iface for iface in interfaces 
                      if any(iface.startswith(p) for p in prefixes)])
                
    except PermissionError:
        print(f"Warning: Permission denied accessing {net_dir}")
        return []
    except Exception as e:
        print(f"Warning: Error listing interfaces - {str(e)}")
        return []

#print(list_interfaces())

suggestors = {
    "list_interfaces": list_interfaces
}
