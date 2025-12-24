import os
import json
import logging
from datetime import datetime
from btlewrap.bluepy import BluepyBackend
from btlewrap.base import BluetoothBackendException
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

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG)
log = logging.getLogger()


def read(alias, address):
    """
    Read data from a MiFlora sensor.
    """
    for attempt in range(3):
        try:
            log.debug(" reading sensor '%s', attempt %d", alias, attempt + 1)
            poller = MiFloraPoller(address, BluepyBackend)

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
            return

        except (OSError, IOError, ValueError, BluetoothBackendException) as e:
            log.error("failed to read '%s' (%s): %s", alias, address, e.__cause__ or e, exc_info=e)
    log.error("failed to read '%s' (%s) after 3 attempts", alias, address)


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
