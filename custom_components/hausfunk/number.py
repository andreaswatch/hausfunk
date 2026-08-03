"""Number entities for Hausfunk."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AUDIO_GAIN,
    CONF_FPS,
    CONF_HEIGHT,
    CONF_PI_HOST,
    CONF_WIDTH,
    DEFAULT_AUDIO_GAIN,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    DOMAIN,
    NAME,
)
from .coordinator import HausfunkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator: HausfunkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HausfunkNumber(
                coordinator,
                CONF_WIDTH,
                "width",
                "mdi:resize",
                160.0,
                1920.0,
                1.0,
                DEFAULT_WIDTH,
            ),
            HausfunkNumber(
                coordinator,
                CONF_HEIGHT,
                "height",
                "mdi:resize",
                120.0,
                1080.0,
                1.0,
                DEFAULT_HEIGHT,
            ),
            HausfunkNumber(
                coordinator,
                CONF_FPS,
                "fps",
                "mdi:video-input-hdmi",
                1.0,
                60.0,
                1.0,
                DEFAULT_FPS,
            ),
            HausfunkNumber(
                coordinator,
                CONF_AUDIO_GAIN,
                "audio_gain",
                "mdi:microphone-plus",
                0.0,
                10.0,
                0.1,
                DEFAULT_AUDIO_GAIN,
                is_float=True,
            ),
        ]
    )


class HausfunkNumber(CoordinatorEntity, NumberEntity):
    """Number entity for Hausfunk parameters."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HausfunkCoordinator,
        key: str,
        translation_key: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        default_value: float,
        is_float: bool = False,
    ):
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._default_value = default_value
        self._is_float = is_float
        self._attr_unique_id = f"hausfunk_{coordinator.pi_id}_{translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config[CONF_PI_HOST])},
            manufacturer=NAME,
            model="Pi + go2rtc",
            name=f"Hausfunk Pi ({coordinator.config[CONF_PI_HOST]})",
        )

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.config.get(self._key, self._default_value)
        if val is None:
            return None
        return float(val) if self._is_float else int(val)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        target_value = value if self._is_float else int(value)
        await self.coordinator.async_update_setting(self._key, target_value)
