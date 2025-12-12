import json
import paho.mqtt.publish as publish
from logger import log

broker = "localhost"

class Mqtt:

    def execute(self, device, command, data):
        topic = f"device/{device}/{command}"
        result = publish.single(topic, json.dumps(data), hostname=broker)

        return json.dumps({"message": "successful"}), 200
