import os
import json
import re
import signal
import sys
from kef import Kef
from gpio import Gpio
from logger import log
import paho.mqtt.client as mqtt

# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "120"))

MQTT_TOPIC = "device/#"

gpio = Gpio()
kef = Kef()


# The callback for when the client receives a CONNACK response from the server.
def on_connect(_client, _userdata, _flags, rc):
    log.info("connected with result code: '%s'", mqtt.connack_string(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    _client.subscribe(MQTT_TOPIC)

def on_disconnect(_client, _userdata, rc):
    if rc != 0:
        log.error("unexpected disconnection: '%s'", mqtt.error_string(rc))

# The callback for when a PUBLISH message is received from the server.
def on_message(client, _userdata, msg):
    try:
        data = msg.payload.decode("utf-8")
        log.info("received message for topic=%s, data='%s'", msg.topic, data)

        match = re.match(r'device/(.*?)/(.*)', msg.topic.lower())
        device = match.group(1)
        command = match.group(2)

        if command == 'state' or command == 'info':
            return

        if device == "computer":
            state = gpio.execute(device, command, json.loads(data))
            publish(client, device, state)
        elif device == "leopard" or device == "speaker":
            state = kef.execute(command, json.loads(data))
            publish(client, device, state)
        else:
            log.error("unknown device: '%s'", device)

    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        log.error("failure", exc_info=e)

def publish(client, device, state):
    topic = f"device/{device}/state"
    result = client.publish(topic, json.dumps(state))
    log.info("publish message to topic=%s, data='%s', result=%s", topic, state, result)


def exit_gracefully(_signum, _frame):
    log.info("stopping hives")
    gpio.cleanup()
    sys.exit()

########################
# Main
########################
if "__main__" == __name__:
    log.info("starting hives")

    signal.signal(signal.SIGTERM, exit_gracefully)
    signal.signal(signal.SIGINT, exit_gracefully)

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    if mqtt_user:
        mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
        
    mqtt_client.connect(mqtt_broker, mqtt_port, mqtt_timeout)

    # Blocking call that processes network traffic, dispatches callbacks and
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    # handles reconnecting.
    mqtt_client.loop_forever()
