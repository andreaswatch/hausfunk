import json

with open("/home/andreas/.homeassistant/core.device_registry", "r") as f:
    data = json.load(f)

for dev in data["data"]["devices"]:
    if any(i[0] == "hausfunk" for i in dev["identifiers"]):
        print(f"Device ID: {dev['id']}")
        print(f"Name: {dev['name']}")
        print(f"Config Entry ID: {dev['config_entry_id']}")
        print(f"Config Subentry ID: {dev.get('config_subentry_id')}")
        print("---")
