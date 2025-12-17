import os
import json
import paho.mqtt.publish as publish

mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("TEMPERATURE_TOPIC", "sensor/climate/temperature")


class Mqtt:

    def execute(self, device, command, data):
        topic = f"device/{device}/{command}"
        auth = {"username": mqtt_user, "password": mqtt_pass} if mqtt_user else None
        message = json.dumps(data)
        result = publish.single(topic, message, hostname=mqtt_broker, port=mqtt_port, auth=auth)
        success = "successful" if result is None else "unsuccessful"
        return json.dumps({"message": success}), 200
