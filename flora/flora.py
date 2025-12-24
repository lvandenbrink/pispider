import os
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import paho.mqtt.publish as mqtt_publish
import paho.mqtt.client as paho
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

env_file = os.getenv("ENV_FILE", "./config/config.env")
load_dotenv(env_file)

# File of sensors with their addresses
FLORA_SENSORS = os.getenv("FLORA_CONFIG", "sensors.json")

# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("FLORA_TOPIC", "sensor/flora")


# Configure logging
log_file = os.path.join(os.getenv("LOG_DIR", "/var/log"), "flora.log")
log_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2)
log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
log_handler.setLevel(logging.INFO)

log = logging.getLogger("root")
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())


def read(alias, address):
    try:
        poller = MiFloraPoller(address, BluepyBackend)

        if poller.parameter_value(MI_MOISTURE) < 1:
            log.warning("moisture below 1: %s", poller)
            return
    except (BluetoothBackendException) as e:
        log.error("failed to read '%s' (%s): BluetoothBackendException: %s", alias, address, e.__cause__ or e)
        return
    except (OSError, ValueError, RuntimeError) as e:
        log.error("failed to read '%s' (%s)", alias, address, exc_info=e)
        return

    data = {
        "plant": alias,
        "name": poller.name(),
        "moisture": poller.parameter_value(MI_MOISTURE),
        "temperature": poller.parameter_value(MI_TEMPERATURE),
        "light": poller.parameter_value(MI_LIGHT),
        "conductivity": poller.parameter_value(MI_CONDUCTIVITY),
        "battery": poller.parameter_value(MI_BATTERY),
        "firmware": poller.firmware_version(),
        "sensor": "miflora",
        "time": datetime.now().replace(microsecond=0).isoformat()
    }

    publish(alias, data)


def publish(plant, data):
    try:
        topic = f"{mqtt_topic}/{plant}"
        auth = {"username": mqtt_user, "password": mqtt_pass} if mqtt_user else None
        log.debug("publish '%s': %s", topic, data)

        result = mqtt_publish.single(
            topic,
            json.dumps(data),
            hostname=mqtt_broker,
            port=mqtt_port,
            auth=auth,
            retain=True,
        )

        log.info("message publish for '%s' %s", plant, "" if result is None else paho.error_string(result.rc))

    except (OSError, ValueError, RuntimeError, mqtt_publish.MQTTException) as e:
        log.error("failed to publish plant '%s'", plant, exc_info=e)


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
