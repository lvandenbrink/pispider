import os
import json
import time
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
import paho.mqtt.publish as mqtt_publish
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
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

# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_username = os.getenv("MQTT_USERNAME", "")
mqtt_password = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("FLORA_TOPIC", "sensor/flora")


# Configure InfluxDB connection variables
influx_host = os.getenv("INFLUXDB_HOST", "localhost")
influx_port = int(os.getenv("INFLUXDB_PORT", "8086"))
influx_user = os.getenv("INFLUXDB_USER", "user")
influx_password = os.getenv("INFLUXDB_PASSWORD", "")
influx_db = os.getenv("INFLUXDB_FLORA_DATABASE", "flora")

location = os.getenv("LOCATION", "house")

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

        data = {
            "plant": alias,
            "name": poller.name(),
            "moisture": poller.parameter_value(MI_MOISTURE),
            "temperature": poller.parameter_value(MI_TEMPERATURE),
            "light": poller.parameter_value(MI_LIGHT),
            "conductivity": poller.parameter_value(MI_CONDUCTIVITY),
            "battery": poller.parameter_value(MI_BATTERY),
            "firmware": poller.firmware_version(),
            "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        store(alias, data)
        publish(alias, data)

    except (OSError, ValueError, RuntimeError) as e:
        log.error("failed to read '%s' (%s):\n%s", alias, address, e)


def store(alias, data):
    log.info("write mesurement for plant %s: '%s'", alias, data)
    dbdata = {
        "measurement": alias,
        "tags": {"location": "ZV", "node": alias},
        "fields": data,
    }

    try:
        successful = dbclient.write_points([dbdata])
        if not successful:
            log.error("failed to write to db for plant %s", alias)
    except (InfluxDBClientError, InfluxDBServerError) as e:
        log.error("failed to write to db for plant %s", alias, exc_info=e)


def on_disconnect(_client, _userdata, _rc):
    log.info("mqtt client disconnected ok")


def publish(plant, data):
    data["timestamp"] = datetime.now().replace(microsecond=0).isoformat()
    try:
        topic = f"{mqtt_topic}/{plant}"
        auth = {"username": mqtt_username, "password": mqtt_password} if mqtt_username else None
        log.debug("publish `%s`: %s", topic, data)

        result = mqtt_publish.single(
            topic,
            json.dumps(data),
            hostname=mqtt_broker,
            port=mqtt_port,
            auth=auth,
            retain=True,
        )
        if result is None:
            log.info("message published successfully: %s", result)

    except (OSError, ValueError, RuntimeError, mqtt_publish.MQTTException) as e:
        log.error("failed to publish plant %s", plant, exc_info=e)


########################
# Main
########################
if "__main__" == __name__:
    # Set up a client for InfluxDB
    while True:
        try:
            # Create the InfluxDB client object
            dbclient = InfluxDBClient(
                influx_host, influx_port, influx_user, influx_password, influx_db
            )
            break
        except ConnectionError:
            log.exception("failed to connect to influx")
            time.sleep(120)

    # read sensor devices
    sensors = {}
    with open(FLORA_SENSORS, encoding="utf-8") as f:
        sensors = json.load(f)

    for sensor_alias, sensor_address in sensors.items():
        if sensor_alias.startswith("#"):
            log.info("skip: %s", sensor_alias)
            continue
        read(sensor_alias, sensor_address)
