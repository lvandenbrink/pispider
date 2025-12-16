# DSMR P1 reading
# 12-2018
import os
import time
import logging
import re
import json
import serial
from logging.handlers import RotatingFileHandler
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
import paho.mqtt.client as paho


#########################################################
# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_topic = os.getenv("ENERGY_TOPIC", "sensor/power/p1meter")

#########################################################
# Configure InfluxDB connection variables
influx_host = os.getenv("INFLUXDB_HOST", "localhost")
influx_port = int(os.getenv("INFLUXDB_PORT", "8086"))
influx_user = os.getenv("INFLUXDB_USER", "user")
influx_password = os.getenv("INFLUXDB_PASSWORD", "")
influx_energy_db = os.getenv("INFLUXDB_ENERGY_DATABASE", "energy")

# think of measurement as a SQL table, it's not...but...
measurement = os.getenv("INFLUXDB_ENERGY_MEASUREMENT", "meter")
location = os.getenv("LOCATION", "house")

# Configure logging
log_dir = os.getenv('LOG_DIR', '/var/log')
log_handler = RotatingFileHandler(os.path.join(log_dir, 'electricity-meter.log'),
                                  mode='a',
                                  maxBytes=5*1024*1024,
                                  backupCount=2,
                                  encoding=None,
                                  delay=0)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger('root')
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())


obis_table = {
    r"1-3:0.2.8\((\d+)\)": "version_info",              # Version information for P1 output
    r"0-0:1.0.0\((.*?)\)S": "timestamp",                # Date-time stamp of the P1 message
    # r"0-0:96.1.1\((\d+)\)": "equipment_identifier",   # Equipment identifier
    r"1-0:1.8.1\((.*?)\*kWh\)": "meter_t1",             # Meter Reading electricity delivered to client (Tariff 1) in 0,001 kWh
    r"1-0:1.8.2\((.*?)\*kWh\)": "meter_t2",             # Meter Reading electricity delivered to client (Tariff 2) in 0,001 kWh
    r"1-0:2.8.1\((.*?)\*kWh\)": "meter_back_t1",        # Meter Reading electricity delivered by client (Tariff 1) in 0,001 kWh
    r"1-0:2.8.2\((.*?)\*kWh\)": "meter_back_t2",        # Meter Reading electricity delivered by client (Tariff 2) in 0,001 kWh
    r"0-0:96.14.0\((\d+)\)": "tariff_indicator",        # Tariff indicator electricity. The tariff indicator can also be used to switch tariff dependent loads e.g boilers. This is the responsibility of the P1 user
    r"1-0:1.7.0\((.*?)\*kW\)": "electricity_delivered", # Actual electricity power delivered (+P) in 1 Watt resolution
    r"1-0:2.7.0\((.*?)\*kW\)": "electricity_received",  # Actual electricity power received (-P) in 1 Watt resolution
    r"0-0:96.7.21\((\d+)\)": "power_failures",          # Number of power failures in any phase
    r"0-0:96.7.9\((\d+)\)": "long_power_failures",      # Number of long power failures in any phase
    # r"1-0:99.97.0(.*?)": "failure_events",              # Power Failure Event Log (long power failures)
    r"1-0:32.32.0\((\d+)\)": "number_voltage_sags1",    # Number of voltage sags in phase L1
    r"1-0:52.32.0\((\d+)\)": "number_voltage_sags2",    # Number of voltage sags in phase L2
    r"1-0:72.32.0\((\d+)\)": "number_voltage_sags3",    # Number of voltage sags in phase L3
    r"1-0:32.36.0\((\d+)\)": "number_voltage_swells1",  # Number of voltage swells in phase L1
    r"1-0:52.36.0\((\d+)\)": "number_voltage_swells2",  # Number of voltage swells in phase L2
    r"1-0:72.36.0\((\d+)\)": "number_voltage_swells3",  # Number of voltage swells in phase L3
    # r"0-0:96.13.0\((.*?)\)": "text_message",            # Text message max 1024 characters.
    r"1-0:32.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l1",  # Instantaneous voltage L1 in V resolution
    r"1-0:52.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l2",  # Instantaneous voltage L2 in V resolution
    r"1-0:72.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l3",  # Instantaneous voltage L3 in V resolution
    r"1-0:31.7.0\((\d+)\*A\)": "instantaneous_current_l1",      # Instantaneous current L1 in A resolution.
    r"1-0:51.7.0\((\d+)\*A\)": "instantaneous_current_l2",      # Instantaneous current L2 in A resolution.
    r"1-0:71.7.0\((\d+)\*A\)": "instantaneous_current_l3",      # Instantaneous current L3 in A resolution.
    r"1-0:21.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power1", # Instantaneous active power L1 (+P) in W resolution
    r"1-0:41.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power2", # Instantaneous active power L2 (+P) in W resolution
    r"1-0:61.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power3", # Instantaneous active power L3 (+P) in W resolution
    r"1-0:22.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power1", # Instantaneous active power L1 (-P) in W resolution
    r"1-0:42.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power2", # Instantaneous active power L2 (-P) in W resolution
    r"1-0:62.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power3", # Instantaneous active power L3 (-P) in W resolution
    r"0-1:24.1.0\((\d+)\)": "gas_device_type",              # Device type (gas)
    # r"0-1:96.1.0\((\d+)\)": "gas_equipment_identifier",     # Equipment identifier (gas)
    r"0-1:24.2.1\(.*?\)\((.*?)\*m3\)": "gas_meter"          # Last 5-minute Meter reading in 0,001 m3 and capture time
}

def parse_datagram(data):
    results = {}
    for line in data:
        for regex,key in obis_table.items():
            try:
                match = re.match(regex, line)
                if match:
                    value = match.group(1)

                    if re.fullmatch(r"\d+", value):
                        value = int(value)
                    elif re.fullmatch(r"\d+\.\d+", value):
                        value = float(value)

                    results[key] = value
                    break  # move to next line after first match
            except (re.error, IndexError) as e:
                log.error("Failed to match regex '%s' on line: %s", regex, line, exc_info=e)
    return results

def datagram(client, lines):
    iso = time.ctime()
    log.debug("===========================================================")
    log.info("handle datagram: %s", iso)
    log.debug("%s", lines)
    log.debug("===========================================================")

    results = parse_datagram(lines)
    if not results:
        log.warning("no results found in datagram")
        return client

    # Publish to MQTT
    for key, value in results.items():
        client = publish(client, key, value)

    # Write to InfluxDB
    attempts = 0
    while attempts < 3:
        try:
            # Create the JSON data structure
            data = [{
                "measurement": measurement,
                "tags": {
                    "location": location,
                },
                "fields": results
            }]

            # Send the JSON data to InfluxDB
            log.debug("data = %s", json.dumps(data, indent=2))
            client.write_points(data)
            break
        except (InfluxDBClientError, InfluxDBServerError) as e:
            log.error("InfluxDB client/server error writing to influxdb", exc_info=e)
            attempts += 1
            time.sleep(5)
        except (ValueError, TypeError, OSError) as e:
            log.error("Unexpected error writing to influxdb", exc_info=e)
            break
    return client

def read(client):
    ser = serial.Serial()
    ser.baudrate = 115200
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.xonxoff=0
    ser.rtscts=0
    ser.timeout=20
    ser.port="/dev/ttyS0"

    log.info("serial communication initialized for: %s", ser.portstr)

    try :
        ser.open()
        lines = []
        while True:
            line = ser.readline()
            if (line.startswith(b'/KFM5KAIFA-METER')): # Header information
                client = datagram(client, lines)
                lines = []
            elif (not line.startswith(b'\r\n')):
                lines.append(line.decode().strip())
    except UnicodeDecodeError as e:
        log.error("failed to decode line %r", line, exc_info=e)
    except KeyboardInterrupt:
        log.error("Serial reading manually stopped.")
    except (serial.SerialException, OSError) as e:
        log.error("Error while opening or reading the serial port %s.", ser.name, exc_info=e)
    finally:
        ser.close()


def on_disconnect(_client, _userdata, _rc):
   log.info("mqtt client disconnected ok")

def publish(client, field, value):
    try:
        if client is None:
            client = paho.Client("p1meter")
            client.on_disconnect = on_disconnect
            client.connect(mqtt_broker, mqtt_port)

        topic = f"{mqtt_topic}/{field}"
        log.debug("publish `%s`: %s", topic, value)
        client.publish(topic, value, retain=True)
        return client
    except (paho.WebsocketConnectionError, OSError, ValueError) as e:
        log.exception(e)
        return client

if __name__ == '__main__':
    log.info("start reading the DSMR P1" )

    while True:
        try:
            # Create the InfluxDB client object
            mqtt_client = InfluxDBClient(influx_host, influx_port, influx_user, influx_password, influx_energy_db)
            break
        except ConnectionError:
            log.exception("failed to connect to influx")
            time.sleep(120)

    read(mqtt_client)
