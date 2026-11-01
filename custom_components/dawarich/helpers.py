"""Helper functions for the Dawarich integration."""

from dawarich_api import DawarichAPI
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

try:
    from homeassistant.components.hassio import is_hassio
except ImportError:

    def is_hassio(hass: HomeAssistant) -> bool:
        """Fallback when hassio is unavailable."""
        return False


def is_hassio_environment(hass: HomeAssistant) -> bool:
    """Check if Home Assistant is running in a Hass.io / Supervisor environment."""
    return is_hassio(hass)


def get_addon_by_host(hass: HomeAssistant, host: str) -> str | None:
    """Return the add-on update entity ID if the given host corresponds to an installed Dawarich add-on."""
    if not is_hassio_environment(hass):
        return None

    host_clean = host.split(":", maxsplit=1)[0].strip().lower()

    registry = er.async_get(hass)
    dawarich_addon_entities: list[er.RegistryEntry] = []
    for entity in registry.entities.values():
        if entity.domain == "update" and entity.platform == "hassio":
            unique_id_lower = (entity.unique_id or "").lower()
            entity_id_lower = entity.entity_id.lower()
            name_lower = (entity.original_name or "").lower()
            if (
                "dawarich" in unique_id_lower
                or "dawarich" in entity_id_lower
                or "dawarich" in name_lower
            ):
                dawarich_addon_entities.append(entity)

    if not dawarich_addon_entities:
        return None

    # Check if host matches any candidate add-on slug or hostname
    for entity in dawarich_addon_entities:
        slug = (entity.unique_id or "").removeprefix("addon_").lower()
        addon_hostname = slug.replace("_", "-")
        if host_clean in (addon_hostname, slug, "dawarich"):
            return entity.entity_id

    # If the host is loopback or local container name and a Dawarich add-on is installed
    if host_clean in ("localhost", "127.0.0.1", "::1", "dawarich"):
        return dawarich_addon_entities[0].entity_id

    # Check if host is internal hostname containing dawarich
    if "dawarich" in host_clean and (
        host_clean.endswith(".local") or "." not in host_clean
    ):
        return dawarich_addon_entities[0].entity_id

    return None


def get_api(host: str, api_key: str, use_ssl: bool, verify_ssl: bool) -> DawarichAPI:
    """Get the API object."""
    url = host.removeprefix("http://").removeprefix("https://")
    if use_ssl:
        url = f"https://{url}"
    else:
        url = f"http://{url}"
    return DawarichAPI(url=url, api_key=api_key, verify_ssl=verify_ssl)
