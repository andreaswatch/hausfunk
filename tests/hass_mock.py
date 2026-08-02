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
device_registry_mock = MagicMock()
device_registry_mock.DeviceInfo = dict

sys.modules["homeassistant"] = ha_mock
sys.modules["homeassistant.core"] = core_mock
sys.modules["homeassistant.config_entries"] = config_entries_mock
sys.modules["homeassistant.const"] = const_mock
sys.modules["homeassistant.helpers"] = helpers_mock
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator_mock
sys.modules["homeassistant.helpers.device_registry"] = device_registry_mock
sys.modules["homeassistant.components"] = MagicMock()

# Third-party libs used by the component that are not installed locally
sys.modules["asyncssh"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
