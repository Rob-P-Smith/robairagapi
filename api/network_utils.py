"""
Network utility functions for robairagapi
Handles MAC address lookups and network validation
"""

import re
from typing import Optional
from pathlib import Path


def get_mac_address_from_ip(ip_address: str) -> Optional[str]:
    """
    Get MAC address for given IP from ARP cache.

    Args:
        ip_address: IP address to lookup (e.g., "192.168.10.1")

    Returns:
        MAC address in format "aa:bb:cc:dd:ee:ff" or None if not found
    """
    try:
        # Read ARP cache from /proc/net/arp (Linux)
        arp_file = Path("/proc/net/arp")
        if not arp_file.exists():
            return None

        with open(arp_file, "r") as f:
            lines = f.readlines()

        # Skip header line
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                # Format: IP address, HW type, Flags, HW address, Mask, Device
                line_ip = parts[0]
                hw_address = parts[3]

                if line_ip == ip_address:
                    # Validate MAC address format
                    if re.match(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$', hw_address, re.IGNORECASE):
                        return hw_address.lower()

        return None

    except Exception as e:
        print(f"Warning: Failed to lookup MAC for {ip_address}: {e}")
        return None


def validate_mac_address(mac_address: str) -> bool:
    """
    Validate MAC address format.

    Args:
        mac_address: MAC address string

    Returns:
        True if valid MAC format, False otherwise
    """
    if not mac_address:
        return False

    # Standard MAC format: aa:bb:cc:dd:ee:ff
    pattern = r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$'
    return bool(re.match(pattern, mac_address.lower()))


def ip_in_subnet(ip: str, subnet: str) -> bool:
    """
    Check if IP address is in subnet (basic CIDR check).

    Args:
        ip: IP address (e.g., "192.168.10.50")
        subnet: CIDR subnet (e.g., "192.168.10.0/24")

    Returns:
        True if IP is in subnet, False otherwise
    """
    try:
        # Simple implementation for IPv4 /24 subnets
        if '/' not in subnet:
            return False

        network, prefix_len = subnet.split('/')
        prefix_len = int(prefix_len)

        # Only support /24 for simplicity (common LAN subnet)
        if prefix_len != 24:
            return False

        # Compare first 3 octets
        ip_octets = ip.split('.')
        network_octets = network.split('.')

        if len(ip_octets) != 4 or len(network_octets) != 4:
            return False

        return ip_octets[:3] == network_octets[:3]

    except Exception:
        return False
