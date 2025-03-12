"""Helper functions for the Dawarich integration."""

from dawarich_api import DawarichAPI


def get_api(host: str, api_key: str, use_ssl: bool, verify_ssl: bool) -> DawarichAPI:
    """Get the API object."""
    url = host.removeprefix("http://").removeprefix("https://")
    if use_ssl:
        url = f"https://{url}"
    else:
        url = f"http://{url}"
    return DawarichAPI(url=url, api_key=api_key, verify_ssl=verify_ssl)
