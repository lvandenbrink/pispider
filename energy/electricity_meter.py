# DSMR P1 reading
# 12-2018
import os
import time
import logging
import re
import json
from logging.handlers import RotatingFileHandler
import serial
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
import paho.mqtt.client as paho


#########################################################
# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_user = os.getenv("MQTT_USERNAME", "")
mqtt_pass = os.getenv("MQTT_PASSWORD", "")
mqtt_topic = os.getenv("ENERGY_TOPIC", "sensor/power/p1meter")
mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "120"))

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

# Tolerance to allow for float noise when checking that cumulative counters that only increase.
MONOTONIC_TOLERANCE = float(os.getenv("MONOTONIC_TOLERANCE", "0.01"))

# Cumulative counters that never decrease.
MONOTONIC_FIELDS = {
    "meter_t1",
    "meter_t2",
    "meter_back_t1",
    "meter_back_t2",
    "gas_meter",
}

# Configure logging
log_dir = os.path.join(os.getenv("LOG_DIR", "/var/log"), "electricity-meter.log")
log_handler = RotatingFileHandler(
    log_dir, mode="a", maxBytes=5 * 1024 * 1024, backupCount=2
)
log_formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s"
)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger("root")
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())


obis_table = {
    r"1-3:0.2.8\((\d+)\)": "version_info",  # Version information for P1 output
    r"0-0:1.0.0\((.*?)\)S": "timestamp",  # Date-time stamp of the P1 message
    # r"0-0:96.1.1\((\d+)\)": "equipment_identifier",   # Equipment identifier
    r"1-0:1.8.1\((.*?)\*kWh\)": "meter_t1",  # Meter Reading electricity delivered to client (Tariff 1) in 0,001 kWh
    r"1-0:1.8.2\((.*?)\*kWh\)": "meter_t2",  # Meter Reading electricity delivered to client (Tariff 2) in 0,001 kWh
    r"1-0:2.8.1\((.*?)\*kWh\)": "meter_back_t1",  # Meter Reading electricity delivered by client (Tariff 1) in 0,001 kWh
    r"1-0:2.8.2\((.*?)\*kWh\)": "meter_back_t2",  # Meter Reading electricity delivered by client (Tariff 2) in 0,001 kWh
    r"0-0:96.14.0\((\d+)\)": "tariff_indicator",  # Tariff indicator electricity. The tariff indicator can also be used to switch tariff dependent loads e.g boilers. This is the responsibility of the P1 user
    r"1-0:1.7.0\((.*?)\*kW\)": "electricity_delivered",  # Actual electricity power delivered (+P) in 1 Watt resolution
    r"1-0:2.7.0\((.*?)\*kW\)": "electricity_received",  # Actual electricity power received (-P) in 1 Watt resolution
    r"0-0:96.7.21\((\d+)\)": "power_failures",  # Number of power failures in any phase
    r"0-0:96.7.9\((\d+)\)": "long_power_failures",  # Number of long power failures in any phase
    # r"1-0:99.97.0(.*?)": "failure_events",              # Power Failure Event Log (long power failures)
    r"1-0:32.32.0\((\d+)\)": "number_voltage_sags1",  # Number of voltage sags in phase L1
    r"1-0:52.32.0\((\d+)\)": "number_voltage_sags2",  # Number of voltage sags in phase L2
    r"1-0:72.32.0\((\d+)\)": "number_voltage_sags3",  # Number of voltage sags in phase L3
    r"1-0:32.36.0\((\d+)\)": "number_voltage_swells1",  # Number of voltage swells in phase L1
    r"1-0:52.36.0\((\d+)\)": "number_voltage_swells2",  # Number of voltage swells in phase L2
    r"1-0:72.36.0\((\d+)\)": "number_voltage_swells3",  # Number of voltage swells in phase L3
    # r"0-0:96.13.0\((.*?)\)": "text_message",            # Text message max 1024 characters.
    r"1-0:32.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l1",  # Instantaneous voltage L1 in V resolution
    r"1-0:52.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l2",  # Instantaneous voltage L2 in V resolution
    r"1-0:72.7.0\(([\d\.]+)\*V\)": "instantaneous_voltage_l3",  # Instantaneous voltage L3 in V resolution
    r"1-0:31.7.0\((\d+)\*A\)": "instantaneous_current_l1",  # Instantaneous current L1 in A resolution.
    r"1-0:51.7.0\((\d+)\*A\)": "instantaneous_current_l2",  # Instantaneous current L2 in A resolution.
    r"1-0:71.7.0\((\d+)\*A\)": "instantaneous_current_l3",  # Instantaneous current L3 in A resolution.
    r"1-0:21.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power1",  # Instantaneous active power L1 (+P) in W resolution
    r"1-0:41.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power2",  # Instantaneous active power L2 (+P) in W resolution
    r"1-0:61.7.0\((.*?)\*kW\)": "instantaneous_active_positive_power3",  # Instantaneous active power L3 (+P) in W resolution
    r"1-0:22.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power1",  # Instantaneous active power L1 (-P) in W resolution
    r"1-0:42.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power2",  # Instantaneous active power L2 (-P) in W resolution
    r"1-0:62.7.0\((.*?)\*kW\)": "instantaneous_active_negative_power3",  # Instantaneous active power L3 (-P) in W resolution
    r"0-1:24.1.0\((\d+)\)": "gas_device_type",  # Device type (gas)
    # r"0-1:96.1.0\((\d+)\)": "gas_equipment_identifier",     # Equipment identifier (gas)
    r"0-1:24.2.1\(.*?\)\((.*?)\*m3\)": "gas_meter",  # Last 5-minute Meter reading in 0,001 m3 and capture time
}


class EnergyMonitor:

    def __init__(self):
        self.last_values = {}
        self.init_influxdb()
        self.init_mqtt_client()

    def init_influxdb(self):
        # Create the InfluxDB client object
        while True:
            try:
                self.influx_client = InfluxDBClient(
                    influx_host,
                    influx_port,
                    influx_user,
                    influx_password,
                    influx_energy_db,
                )
                break
            except ConnectionError:
                log.exception("failed to connect to influx")
                time.sleep(120)

    def init_mqtt_client(self):
        # Create the MQTT client object
        self.mqtt_client = paho.Client()
        self.mqtt_client.on_disconnect = self.on_disconnect

        if mqtt_user:
            self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)

        self.mqtt_client.connect(mqtt_broker, mqtt_port, mqtt_timeout)

    def start(self):
        ser = serial.Serial()
        ser.baudrate = 115200
        ser.bytesize = serial.EIGHTBITS
        ser.parity = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.xonxoff = 0
        ser.rtscts = 0
        ser.timeout = 20
        ser.port = "/dev/ttyS0"

        log.info("serial communication initialized for: %s", ser.portstr)

        try:
            ser.open()
            raw_lines = []
            while True:
                raw = ser.readline()
                if raw.startswith(b"/KFM5KAIFA-METER"):  # Header: start of a new telegram
                    raw_lines = [raw]
                    continue

                if not raw_lines:
                    # Haven't seen a header yet; ignore stray bytes.
                    continue

                raw_lines.append(raw)

                if raw.startswith(b"!"):  # Checksum line: end of telegram
                    self.datagram(raw_lines)
                    raw_lines = []
        except KeyboardInterrupt:
            log.error("Serial reading manually stopped.")
        except (serial.SerialException, OSError) as e:
            log.error(
                "Error while opening or reading the serial port %s.",
                ser.name,
                exc_info=e,
            )
        finally:
            ser.close()

    def calc_crc16(self, data: bytes) -> int:
        """CRC16/ARC checksum as used in the DSMR P1 telegram trailer."""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def verify_checksum(self, telegram: bytes) -> bool:
        """
        Verify the CRC16 trailer of a raw DSMR telegram. The checksum covers all bytes from the header up to and including the '!' marker; it is followed by 4 hex digits.
        """
        idx = telegram.rfind(b"!")
        if idx == -1:
            log.warning("no checksum marker ('!') found in telegram")
            return False

        data_part = telegram[: idx + 1]
        checksum_part = telegram[idx + 1 : idx + 5].strip()

        try:
            expected = int(checksum_part, 16)
        except ValueError:
            log.warning("malformed checksum field: %r", checksum_part)
            return False

        actual = self.calc_crc16(data_part)
        if actual != expected:
            log.error("checksum mismatch: computed 0x%04X, telegram claims 0x%04X",actual,expected)
        return actual == expected

    def datagram(self, raw_lines):
        full_telegram = b"".join(raw_lines)

        checksum_ok = self.verify_checksum(full_telegram)
        if not checksum_ok:
            # Discard the whole telegram if the checksum is not ok
            log.error("checksum mismatch, datagram: %s", raw_lines)
            return
        try:
            lines = [line.decode().strip() for line in raw_lines]
        except UnicodeDecodeError as e:
            log.error("failed to decode checksum-verified telegram", exc_info=e)
            return

        iso = time.ctime()
        log.debug("===========================================================")
        log.info("handle datagram: %s", iso)
        log.debug("%s", lines)
        log.debug("===========================================================")

        results = self.parse_datagram(lines)
        if not results:
            log.warning("no results found in datagram")
            return

        # Publish to MQTT
        for key, value in results.items():
            self.publish(key, value)

        # Write to InfluxDB
        attempts = 0
        while attempts < 3:
            try:
                # Create the JSON data structure
                data = [
                    {
                        "measurement": measurement,
                        "tags": {
                            "location": location,
                        },
                        "fields": results,
                    }
                ]

                # Send the JSON data to InfluxDB
                log.debug("data = %s", json.dumps(data, indent=2))
                self.influx_client.write_points(data)
                break
            except (InfluxDBClientError, InfluxDBServerError) as e:
                log.error(
                    "InfluxDB client/server error writing to influxdb", exc_info=e
                )
                attempts += 1
                time.sleep(5)
            except (ValueError, TypeError, OSError) as e:
                log.error("Unexpected error writing to influxdb", exc_info=e)
                break

    def parse_datagram(self, data):
        results = {}
        for line in data:
            for regex, key in obis_table.items():
                try:
                    match = re.match(regex, line)
                    if not match:
                        continue

                    value = match.group(1)

                    if re.fullmatch(r"\d+", value):
                        value = int(value)
                    elif re.fullmatch(r"\d+\.\d+", value):
                        value = float(value)

                    if key in MONOTONIC_FIELDS and not self.is_plausible_monotonic(
                        key, value
                    ):
                        # Skip this field only; the rest of the (checksum-valid)
                        # telegram is still trustworthy.
                        break

                    if key in MONOTONIC_FIELDS:
                        self.last_values[key] = value

                    results[key] = value
                    break  # move to next line after first match
                except (re.error, IndexError) as e:
                    log.error(
                        "Failed to match regex '%s' on line: %s",
                        regex,
                        line,
                        exc_info=e,
                    )
        return results

    def is_plausible_monotonic(self, key, value):
        """
        Reject a cumulative-counter reading that decreases from the last
        known-good value by more than a small tolerance. Returns True if the
        value is acceptable.
        """
        prev = self.last_values.get(key)
        if prev is None:
            return True  # no baseline yet, accept and establish one

        if value < prev - MONOTONIC_TOLERANCE:
            log.warning(
                "rejected implausible reading for %s: %s < previous %s (tolerance %s)",
                key,
                value,
                prev,
                MONOTONIC_TOLERANCE,
            )
            return False

        return True

    def publish(self, field, value):
        try:
            if self.mqtt_client is None or not self.mqtt_client.is_connected():
                self.init_mqtt_client()

            topic = f"{mqtt_topic}/{field}"
            log.debug("publish `%s`: %s", topic, value)
            result = self.mqtt_client.publish(topic, value, retain=True)
            if result.rc != paho.MQTT_ERR_SUCCESS:
                log.error("failed to publish to topic %s: %s", topic, paho.error_string(result.rc))

        except (paho.WebsocketConnectionError, OSError, ValueError) as e:
            log.exception(e)

    def on_disconnect(self, _client, _userdata, _rc, _properties=None):
        log.info("mqtt client disconnected ok")


if __name__ == "__main__":
    log.info("start reading the DSMR P1")

    monitor = EnergyMonitor()
    monitor.start()
