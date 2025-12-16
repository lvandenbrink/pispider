import os
import json
from logger import log
import RPi.GPIO as GPIO
import paho.mqtt.publish as publish

mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_username = os.getenv("MQTT_USERNAME", "")
mqtt_password = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("MQTT_HIVES_TOPIC", "device/#")

COMPUTER = "computer"
DEVICES = {
    COMPUTER: 23
}

POWER = 13
B1 = 16
B2 = 12
B3 = 21
B4 = 19
POWER4 = 26

class Gpio:
    def __init__(self):
        log.debug("setup devices %s", DEVICES)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DEVICES[COMPUTER], GPIO.OUT)
        GPIO.output(DEVICES[COMPUTER], GPIO.HIGH)

        GPIO.setup(POWER, GPIO.OUT)
        GPIO.setup(POWER4, GPIO.OUT)

        GPIO.output(POWER, GPIO.LOW)
        GPIO.output(POWER4, GPIO.LOW)

        GPIO.setup(B1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(B2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(B1,GPIO.FALLING,callback=self.button_callback, bouncetime=600)
        GPIO.add_event_detect(B2,GPIO.FALLING,callback=self.button_callback, bouncetime=600)

        self.state = {}
        self.state[COMPUTER] = GPIO.HIGH

    def cleanup(self):
        log.info("destroy: turn off and cleanup  pins %s", DEVICES)
        # GPIO.output(DEVICES[COMPUTER], GPIO.LOW) # power off
        GPIO.cleanup()

    def execute(self, device, command, action):
        if not device in DEVICES:
            return "error: unkonwn device"

        if command in ("get", "info"):
            # skip just return info
            pass
        elif command == "set":
            state = action['state']
            if state not in ('on', 'off'):
                log.error("gpio %s: unknown state '%s'", device, state)
                return { "errorCode": "offline", "status" : "ERROR" }

            self.state[device] = GPIO.HIGH if state == 'on' else GPIO.LOW
            GPIO.output(DEVICES[device], self.state[device])
        elif command == "toggle":
            self.state[device] = GPIO.HIGH if self.state[device] == GPIO.LOW else GPIO.LOW
            GPIO.output(DEVICES[device], self.state[device])
        else:
            log.error("gpio %s: unknown command '%s'", device, command)
            return { "errorCode": "offline", "status" : "ERROR" }

        info = {
            'state': 'on' if self.state[device] == GPIO.HIGH else 'off'
        }

        log.info("device '%s' with action '%s' to state: %s", device, action, info)
        return info

    def button_callback(self, channel):
        log.info("button was pushed: %s", channel)
        if channel == B1:
            self.send_command(COMPUTER, "toggle", {})
        if channel == B2:
            self.send_command("speaker", "toggle", {})

    def send_command(self, device, command, data):
        topic = f"device/{device}/{command}"
        auth = {'username': mqtt_username, 'password': mqtt_password} if mqtt_username else None
        publish.single(topic, json.dumps(data), hostname=mqtt_broker, port=mqtt_port, auth=auth)
