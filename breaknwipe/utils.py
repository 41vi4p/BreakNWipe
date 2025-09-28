"""
Utility functions for BreakNWipe.
"""

import socket
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)


def check_internet_connectivity(timeout: int = 5) -> bool:
    """
    Check if internet connectivity is available.

    Args:
        timeout: Timeout in seconds for the connectivity check

    Returns:
        True if internet is available, False otherwise
    """
    # List of reliable hosts to check
    test_hosts = [
        "8.8.8.8",  # Google DNS
        "1.1.1.1",  # Cloudflare DNS
        "208.67.222.222"  # OpenDNS
    ]

    # Try DNS resolution first (fastest)
    for host in test_hosts:
        try:
            socket.create_connection((host, 53), timeout=timeout).close()
            logger.debug(f"Internet connectivity confirmed via {host}")
            return True
        except (socket.timeout, socket.error):
            continue

    # Fallback: Try HTTP connection to reliable services
    test_urls = [
        "https://www.google.com",
        "https://httpbin.org/status/200",
        "https://www.cloudflare.com"
    ]

    for url in test_urls:
        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            if response.getcode() == 200:
                logger.debug(f"Internet connectivity confirmed via {url}")
                return True
        except (urllib.error.URLError, socket.timeout):
            continue

    logger.debug("No internet connectivity detected")
    return False


def check_blockchain_service_connectivity(rpc_url: str, timeout: int = 10) -> bool:
    """
    Check if blockchain RPC service is reachable.

    Args:
        rpc_url: Blockchain RPC URL to test
        timeout: Timeout in seconds

    Returns:
        True if blockchain service is reachable, False otherwise
    """
    try:
        import json
        import urllib.request
        import urllib.parse

        # Prepare a simple JSON-RPC request to test connectivity
        data = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }

        # Convert to JSON and encode
        json_data = json.dumps(data).encode('utf-8')

        # Create request
        req = urllib.request.Request(
            rpc_url,
            data=json_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'BreakNWipe/1.0'
            }
        )

        # Test connection
        response = urllib.request.urlopen(req, timeout=timeout)
        result = json.loads(response.read().decode('utf-8'))

        # Check if we got a valid response
        if 'result' in result:
            logger.debug(f"Blockchain service connectivity confirmed: {rpc_url}")
            return True
        else:
            logger.debug(f"Blockchain service returned error: {result}")
            return False

    except Exception as e:
        logger.debug(f"Blockchain service connectivity failed for {rpc_url}: {e}")
        return False