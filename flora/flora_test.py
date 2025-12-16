import os
import json
import logging
from datetime import datetime
from btlewrap.bluepy import BluepyBackend
from miflora.miflora_poller import (
    MI_BATTERY,
    MI_CONDUCTIVITY,
    MI_LIGHT,
    MI_MOISTURE,
    MI_TEMPERATURE,
    MiFloraPoller,
)

# File of sensors with their addresses
FLORA_SENSORS = os.getenv("FLORA_CONFIG", "sensors.json")

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
log = logging.getLogger()


def read(alias, address):
    try:
        poller = MiFloraPoller(address, BluepyBackend)

        if poller.parameter_value(MI_MOISTURE) < 1:
            log.warning("moisture below 1: %s", poller)
            return


        data = {
            "name": poller.name(),
            "moisture": poller.parameter_value(MI_MOISTURE),
            "temperature": poller.parameter_value(MI_TEMPERATURE),
            "light": poller.parameter_value(MI_LIGHT),
            "conductivity": poller.parameter_value(MI_CONDUCTIVITY),
            "battery": poller.parameter_value(MI_BATTERY),
            "firmware": poller.firmware_version(),
            "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        log.info("plant %s: '%s'", alias, data)

    except (OSError, IOError, ValueError) as e:
        log.error("failed to read '%s' (%s): %s", alias, address, str(e))


########################
# Main
########################
if "__main__" == __name__:
    # read sensor devices
    sensors = {}
    with open(FLORA_SENSORS, encoding="utf-8") as f:
        sensors = json.load(f)

    for sensor_alias, sensor_address in sensors.items():
        if sensor_alias.startswith("#"):
            log.info("skip: %s", sensor_alias)
            continue
        read(sensor_alias, sensor_address)
