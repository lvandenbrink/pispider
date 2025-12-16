import os
import sys
import json
import signal
import logging
import RPi.GPIO as GPIO
import paho.mqtt.publish as publish

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")

TOP_BUTTON = 6
BOTTOM_BUTTON = 5


logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def top_button_callback(_channel):
    logging.info("top button was pushed")
    send_command("computer", "toggle", {})


def bottom_button_callback(_channel):
    logging.info("bottom button was pushed")
    send_command("speaker", "toggle", {})


def send_command(device, command, data):
    topic = f"device/{device}/{command}"
    result = publish.single(topic, json.dumps(data), hostname=MQTT_BROKER)
    logging.info("sent command to topic `%s`, result: %s", topic, result)


def exit_gracefully(_signum, _frame):
    cleanup()


def cleanup():
    logging.info("exit: cleanup GPIOs")
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGTERM, exit_gracefully)
signal.signal(signal.SIGINT, exit_gracefully)


GPIO.setmode(GPIO.BCM)
GPIO.setup(TOP_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BOTTOM_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.add_event_detect(
    TOP_BUTTON, GPIO.FALLING, callback=top_button_callback, bouncetime=300
)
GPIO.add_event_detect(
    BOTTOM_BUTTON, GPIO.FALLING, callback=bottom_button_callback, bouncetime=300
)

logging.info("start listening")
signal.pause()
