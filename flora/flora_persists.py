import os
import sys
import time
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient


# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("FLORA_TOPIC", "sensor/flora")
mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "120"))

# Configure InfluxDB connection variables
influx_host = os.getenv("INFLUXDB_HOST", "localhost")
influx_port = int(os.getenv("INFLUXDB_PORT", "8086"))
influx_user = os.getenv("INFLUXDB_USER", "user")
influx_password = os.getenv("INFLUXDB_PASSWORD", "")
influx_db = os.getenv("INFLUXDB_FLORA_DATABASE", "flora")

location = os.getenv("LOCATION", "house")

# Configure logging
log_dir = os.path.join(os.getenv("LOG_DIR", "/var/log"), "flora-persists.log")
log_handler = RotatingFileHandler(log_dir, maxBytes=5*1024*1024,backupCount=2)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger('root')
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, _userdata, _flags, rc):
    log.info("connected with result code: '%s'", mqtt.connack_string(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    topic = f"{mqtt_topic}/#"
    client.subscribe(topic)

# The callback for when a PUBLISH message is received from the server.
def on_message(_client, _userdata, msg):
    try:
        device = msg.topic[len(mqtt_topic)-1:]
        message = json.loads(msg.payload.decode("utf-8"))

        if device == 'esp-flora':
            data = {
                'measurement': 'lemon-dracaena',
                'tags': {
                    'location': location,
                     'node': 'lemon-dracaena',
                     'sensor': 'esp'
                },
                'fields': {
                    'plant': 'lemon-dracaena',
                    'temperature': round(float(message['temperature']), 1),
                    'moisture': round(float(message['moisture'])),
                    'time': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                }
            }
        elif message['plant']:
            data = {
                'measurement': message['plant'],
                'tags': {
                    'location': location,
                     'node': message['plant'],
                     'sensor': message['sensor']
                },
                'fields': message
            }
        else:
            log.error("failed to handle update for device=%s, message='%s'", device, message)
            return

        log.info("received update for device=%s, data='%s'", device, data)

        # Send the JSON data to InfluxDB
        successful = dbclient.write_points([data])
        if not successful:
            log.error("failed to write to db for '%s': %s", device, data)

    except (ValueError, KeyError, json.JSONDecodeError, InfluxDBClient.client.InfluxDBClientError) as e:
        log.error("failed to write to db", exc_info=e)

########################
# Main
########################
if "__main__" == __name__:
    log.info("starting flora persist service")
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

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    if mqtt_user:
        mqtt_client.username_pw_set(mqtt_user, mqtt_pass)

    mqtt_client.connect(mqtt_broker, mqtt_port, mqtt_timeout)
    
    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    mqtt_client.loop_forever()

    sys.exit()
