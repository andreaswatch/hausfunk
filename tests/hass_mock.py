import sys
from unittest.mock import MagicMock

# Define real classes for bases to avoid subclassing MagicMock instances
class DummyDataUpdateCoordinator:
    def __init__(self, hass, logger, *, name, update_interval, update_method=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    async def async_config_entry_first_refresh(self):
        pass

    async def async_request_refresh(self):
        pass


class DummyCoordinatorEntity:
    def __init__(self, coordinator, context=None):
        self.coordinator = coordinator

    def _handle_coordinator_update(self) -> None:
        pass

    def async_write_ha_state(self) -> None:
        pass


# Mock Home Assistant modules
ha_mock = MagicMock()
core_mock = MagicMock()
core_mock.callback = lambda f: f

config_entries_mock = MagicMock()
const_mock = MagicMock()

helpers_mock = MagicMock()
update_coordinator_mock = MagicMock()
update_coordinator_mock.DataUpdateCoordinator = DummyDataUpdateCoordinator
update_coordinator_mock.CoordinatorEntity = DummyCoordinatorEntity
update_coordinator_mock.UpdateFailed = Exception
helpers_mock.update_coordinator = update_coordinator_mock
entity_platform_mock = MagicMock()
helpers_mock.entity_platform = entity_platform_mock
device_registry_mock = MagicMock()
device_registry_mock.DeviceInfo = dict

sys.modules["homeassistant"] = ha_mock
sys.modules["homeassistant.core"] = core_mock
sys.modules["homeassistant.config_entries"] = config_entries_mock
sys.modules["homeassistant.const"] = const_mock
sys.modules["homeassistant.helpers"] = helpers_mock
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator_mock
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_mock
sys.modules["homeassistant.helpers.device_registry"] = device_registry_mock
sys.modules["homeassistant.components"] = MagicMock()

# Entity base classes for the platform modules
class DummyEntity:
    _attr_has_entity_name = False
    _attr_unique_id = None
    _attr_device_info = None
    _attr_name = None
    _attr_icon = None

    def __init__(self):
        for attr in ("_attr_has_entity_name", "_attr_unique_id",
                     "_attr_device_info", "_attr_name", "_attr_icon"):
            setattr(self, attr, getattr(type(self), attr, None))

    @property
    def device_info(self):
        return self._attr_device_info

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def icon(self):
        return self._attr_icon

    @property
    def has_entity_name(self):
        return self._attr_has_entity_name


class DummyBinarySensorEntity(DummyEntity):
    def __init__(self):
        super().__init__()
        self._attr_is_on = None

    @property
    def is_on(self):
        return self._attr_is_on


class DummySwitchEntity(DummyEntity):
    def __init__(self):
        super().__init__()
        self._attr_is_on = None

    @property
    def is_on(self):
        return self._attr_is_on

    async def async_turn_on(self, **kwargs):
        pass

    async def async_turn_off(self, **kwargs):
        pass


components_mock = MagicMock()
components_mock.binary_sensor.BinarySensorEntity = DummyBinarySensorEntity
components_mock.switch.SwitchEntity = DummySwitchEntity


class DummyCameraEntity(DummyEntity):
    _attr_supported_features = 0

    def __init__(self):
        super().__init__()
        self._stream_source = None

    @property
    def stream_source(self):
        return self._stream_source

    @property
    def supported_features(self):
        return self._attr_supported_features


components_mock.camera.Camera = DummyCameraEntity
components_mock.camera.CameraEntityFeature = type(
    "CameraEntityFeature", (), {"STREAM": 1}
)
sys.modules["homeassistant.components.binary_sensor"] = components_mock.binary_sensor
sys.modules["homeassistant.components.switch"] = components_mock.switch
sys.modules["homeassistant.components.camera"] = components_mock.camera

# Third-party libs used by the component that are not installed locally
sys.modules["asyncssh"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
