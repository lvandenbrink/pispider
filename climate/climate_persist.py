import os
import re
import sys
import json
import time
import logging
from logging.handlers import RotatingFileHandler
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError

# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("CLIMATE_TOPIC", "sensor/climate")
mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "120"))

# Configure InfluxDB connection variables
influx_host = os.getenv("INFLUXDB_HOST", "localhost")
influx_port = int(os.getenv("INFLUXDB_PORT", "8086"))
influx_user = os.getenv("INFLUXDB_USER", "user")
influx_password = os.getenv("INFLUXDB_PASSWORD", "")
influx_db = os.getenv("INFLUXDB_CLIMATE_DATABASE", "climate")

location = os.getenv("LOCATION", "house")

# Configure logging
log_dir = os.path.join(os.getenv("LOG_DIR", "/var/log"), "climate.log")
log_handler = RotatingFileHandler(log_dir, maxBytes=5 * 1024 * 1024, backupCount=2)
log_formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger("root")
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())


def prepare_data(device, entry):
    try:
        if device == "operame":
            match = re.search(r"(\d+).*", entry, re.IGNORECASE)
            if match:
                data = {
                    "measurement": device,
                    "tags": {
                        "location": location,
                        "devices": "operame",
                        "sensor": "metriful",
                    },
                    "fields": {"co2": int(match.group(1))},
                }
            else:
                log.error("failed to receive correct format from operame: %s", entry)
                return None
        elif device == "esp32":
            fields = json.loads(entry)
            data = {
                "measurement": "esp32",
                "tags": {"location": location, "devices": "esp32", "sensor": "esp32"},
                "fields": fields,
            }
        elif device.startswith("esp"):
            fields = json.loads(entry)
            if "humidity" in fields:
                fields["humidity"] = float(fields["humidity"])
            data = {
                "measurement": device,
                "tags": {"location": location, "devices": device, "sensor": device},
                "fields": fields,
            }
        else:
            data = json.loads(entry)
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as e:
        log.error("failed to read data from '%s': %s", device, entry, exc_info=e)
        return None

    return data


def store(device, data):
    # Send the JSON data to InfluxDB
    try:
        successful = dbclient.write_points([data])
        if not successful:
            log.error("failed to write to db for device '%s': '%s'", device, data)
    except (InfluxDBClientError, InfluxDBServerError) as e:
        log.exception("InfluxDB error occurred: %s", e)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(_client, _userdata, _flags, rc):
    log.info("connected with result code: '%s'", mqtt.connack_string(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    topic = f"{mqtt_topic}/#"
    client.subscribe(topic)


def on_disconnect(_client, _userdata, rc):
    if rc != 0:
        print("unexpected disconnection: ''%s'", mqtt.error_string(rc))


# The callback for when a PUBLISH message is received from the server.
def on_message(_client, _userdata, msg):
    try:
        device = msg.topic[len(mqtt_topic) - 1 :]
        entry = msg.payload.decode("utf-8")

        data = prepare_data(device, entry)
        log.info("received update for device='%s': data=%s", device, data)
        if data is not None:
            store(device, data)

    except (UnicodeDecodeError, AttributeError) as e:
        log.error("failure", exc_info=e)


########################
# Main
########################
if "__main__" == __name__:
    log.info("starting climate persist service")
    # Set up a client for InfluxDB
    while True:
        try:
            # Create the InfluxDB client object
            dbclient = InfluxDBClient(
                influx_host, influx_port, influx_user, influx_password, influx_db
            )
            break
        except ConnectionError:
            logging.exception("failed to connect to influx")
            time.sleep(120)


    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    if mqtt_user:
        client.username_pw_set(mqtt_user, mqtt_pass)

    client.connect(mqtt_broker, mqtt_port, mqtt_timeout)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()

    sys.exit()
