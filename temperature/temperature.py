from os import system
from sys import exit
from glob import glob
from time import sleep
from logging.handlers import RotatingFileHandler
import paho.mqtt.publish as publish
import logging, json, os

#########################################################
# Configure logging
log_dir = os.getenv('LOG_DIR', '/var/log')
log_handler = RotatingFileHandler(f'{log_dir}/temperature.log',
                                  mode='a',
                                  maxBytes=5*1024*1024,
                                  backupCount=2,
                                  encoding=None,
                                  delay=0)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
log_handler.setFormatter(log_formatter)
log_handler.setLevel('INFO')

log = logging.getLogger('root')
log.setLevel('INFO')
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())

#########################################################
# MQTT connection variables
mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
mqtt_username = os.getenv('MQTT_USERNAME', '')
mqtt_password = os.getenv('MQTT_PASSWORD', '')
mqtt_topic = os.getenv('TEMPERATURE_TOPIC', 'sensor/climate/temperature')

location = os.getenv('LOCATION', 'house')
device_name = os.getenv('DEVICE_NAME', 'device')

#########################################################

def read_temp(device_file):
	temperature = read_device(device_file)
	if (temperature is not None):
		log.info("read %s: %f" % (device_file, temperature))
		publish_temp(temperature)

def read_device(device_file):
	with open(device_file, "r") as f:
		data = f.readlines()
		if len(data) < 1 or len(data[0].strip()) < 3 or data[0].strip()[-3:] != "YES":
			log.error("failed to read device '%s': %s" % (device_file, data))
			return None

		return 0.001 * float(data[1].split("=")[1])

def publish_temp(temperature):
	data = {
		'measurement': f'{device_name}',
		'tags': {
			'location': f'{location}',
			'devices': f'{device_name}',
			'sensor': 'DS18B20'
		},
		'fields': {
			"temperature": temperature
		}
	}
	
	# Send data to MQTT
	try:
		msg = json.dumps(data)
		log.info(f"send message to topic `{mqtt_topic}`: {msg}")
		
		# Configure MQTT auth if credentials are provided
		auth = None
		if mqtt_username:
			auth = {'username': mqtt_username, 'password': mqtt_password}
		
		result = publish.single(
			mqtt_topic, 
			msg, 
			hostname=mqtt_broker,
			port=mqtt_port,
			auth=auth
		)
		if result is None:
			log.info("message published successfully: %s", result)
	
	except Exception as e:
		log.exception(e)

if __name__ == "__main__":
	log.info("Starting termpature readings")

	# look for DS18B20 devices
	system('modprobe w1-gpio')
	system('modprobe w1-therm')

	base_dir = '/sys/bus/w1/devices/'
	device_folders = glob(f'{base_dir}[0-9]*')
	device_files = [d + '/w1_slave' for d in device_folders]

	if len(device_files) < 1:
		log.error("failed to find any devices")
		exit("failed to find any devices")

	# keep reading
	while True:
		for device_file in device_files:
			read_temp(device_file)
		sleep(300)
