import RPi.GPIO as GPIO
import paho.mqtt.publish as publish
import logging, signal, json, sys

POWER = 13
B1 = 16
B2 = 20
B3 = 21
B4 = 19
POWER4 = 26

logging.basicConfig(
	format='%(asctime)s %(levelname)-8s %(message)s',
	level=logging.INFO,
	datefmt='%Y-%m-%d %H:%M:%S')

def button_callback(channel):
	logging.info("button was pushed: %s" % channel)

def exit_gracefully(signum, frame):
	cleanup()

def cleanup():
	logging.info("exit: cleanup GPIOs")
	GPIO.cleanup()
	sys.exit(0)

signal.signal(signal.SIGTERM, exit_gracefully)
signal.signal(signal.SIGINT, exit_gracefully)


GPIO.setmode(GPIO.BCM)
GPIO.setup(B1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(B2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(B3, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(B4, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(POWER, GPIO.OUT)
GPIO.setup(POWER4, GPIO.OUT)

GPIO.output(POWER, GPIO.HIGH)
GPIO.output(POWER4, GPIO.HIGH)

GPIO.add_event_detect(B1,GPIO.FALLING,callback=button_callback, bouncetime=300)
GPIO.add_event_detect(B2,GPIO.FALLING,callback=button_callback, bouncetime=300)
GPIO.add_event_detect(B3,GPIO.FALLING,callback=button_callback, bouncetime=300)
GPIO.add_event_detect(B4,GPIO.FALLING,callback=button_callback, bouncetime=300)

logging.info("start listening")
signal.pause()
