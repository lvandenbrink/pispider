#  metriful-publish.py
#
#  Gather metriful data and persist the data in influxdb
# adaptation from cycle_readout
# https://github.com/metriful/sensor
#
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from time import sleep
import paho.mqtt.client as mqtt
from sensor_package.sensor_functions import (
    SensorHardwareSetup,
    get_air_data,
    get_air_quality_data,
    get_light_data,
    get_sound_data,
    SOUND_FREQ_BANDS,
    sound_band_mids_Hz,
    i2c_7bit_address,
    PARTICLE_SENSOR_SELECT_REG,
    PARTICLE_SENSOR,
    CYCLE_TIME_PERIOD_REG,
    CYCLE_PERIOD_100_S,
    CYCLE_MODE_CMD,
    READY_pin,
)

#########################################################
# USER-EDITABLE SETTINGS
# How often to read data (every 3, 100, or 300 seconds)
CYCLE_PERIOD = CYCLE_PERIOD_100_S

# END OF USER-EDITABLE SETTINGS
#########################################################
# MQTT connection variables
mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
mqtt_username = os.getenv("MQTT_USERNAME", "")
mqtt_password = os.getenv("MQTT_PASSWORD", "")
mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "120"))
mqtt_topic = os.getenv("METRIFUL_TOPIC", "sensor/climate/metriful")

location = os.getenv("LOCATION", "house")
device_name = os.getenv("DEVICE_NAME", "device")

#########################################################
# Configure logging
log_dir = os.getenv("LOG_DIR", "/var/log")
log_handler = RotatingFileHandler(
    f"{log_dir}/metriful.log",
    mode="a",
    maxBytes=5 * 1024 * 1024,
    backupCount=2,
    encoding=None,
    delay=0,
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


# The callback for when the client receives a CONNACK response from the server.
def on_connect(mqtt_client, _userdata, _flags, rc):
    """
    Callback for when the client receives a CONNACK response from the MQTT broker.
    Subscribes to the configured MQTT topic upon successful connection.
    """
    log.info("connected with result code: '%s'", mqtt.connack_string(rc))
    mqtt_client.subscribe(mqtt_topic)


def on_disconnect(mqtt_client, _userdata, rc):
    """
    Callback for when the client disconnects from the MQTT broker.
    """
    mqtt_client.loop_stop()
    if rc != 0:
        log.error("unexpected disconnection: '%s'", mqtt.error_string(rc))


def read(mqtt_client, i2c_bus):
    """
    Reads sensor data from the Metriful sensor, formats it, and publishes it to the configured MQTT topic.

    Args:
        mqtt_client: The MQTT client used to publish messages.
        i2c_bus: The I2C bus interface for communicating with the sensor.
    """
    air_data = get_air_data(i2c_bus)
    air_quality_data = get_air_quality_data(i2c_bus)
    light_data = get_light_data(i2c_bus)
    sound_data = get_sound_data(i2c_bus)

    data = {
        "measurement": "metriful",
        "tags": {
            "location": f"{location}",
            "devices": f"{device_name}",
            "sensor": "metriful",
        },
        "fields": {},
    }

    # Air data column order is:
    # Temperature/C, Pressure/Pa, Humidity/%RH, Gas sensor resistance/ohm
    pressure = air_data["P_Pa"] / 100

    data["fields"]["temperature"] = air_data["T"]
    data["fields"]["pressure"] = pressure
    data["fields"]["humidity"] = air_data["H_pc"]
    data["fields"]["gas_sensor_resistance"] = air_data["G_ohm"]

    # write Air quality data
    # Air Quality Index, Estimated CO2/ppm, Equivalent breath VOC/ppm, Accuracy,
    data["fields"]["air_quality_index"] = air_quality_data["AQI"]
    data["fields"]["estimated_co2"] = air_quality_data["CO2e"]
    data["fields"]["equivalent_breath_voc"] = air_quality_data["bVOC"]
    data["fields"]["air_quality_accuracy"] = air_quality_data["AQI_accuracy"]

    # Light data column order is:
    # Illuminance/lux, white light level
    data["fields"]["illuminance"] = light_data["illum_lux"]
    data["fields"]["white_light_level"] = light_data["white"]

    # write sound data column:
    # Sound pressure level/dBA, Sound pressure level for frequency bands 1 to 6 (six columns),
    # Peak sound amplitude/mPa, stability
    data["fields"]["a_weighted_sound_pressure_level"] = sound_data["SPL_dBA"]
    for i in range(0, SOUND_FREQ_BANDS):
        data["fields"]["frequency_band_" + str(sound_band_mids_Hz[i])] = sound_data[
            "SPL_bands_dB"
        ][i]
    data["fields"]["peak_sound_amplitude"] = sound_data["peak_amp_mPa"]

    # Send data to MQTT
    try:
        msg = json.dumps(data)
        (result, _) = mqtt_client.publish(mqtt_topic, msg)
        if result == mqtt.MQTT_ERR_SUCCESS:
            log.info("send message to topic `%s`: %s", mqtt_topic, msg)
        else:
            log.error(
                "failed to send message to topic %s: %s %s", mqtt_topic, result, msg
            )
    except (ValueError, TypeError, mqtt.MQTTException) as e:
        log.exception(e)


########################
# Main
########################
if "__main__" == __name__:
    # Set up a client for MQTT
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.loop_start()
    client.connect(mqtt_broker, mqtt_port, mqtt_timeout)

    # Set up the GPIO and I2C communications bus
    (GPIO, I2C_bus) = SensorHardwareSetup()

    # Apply the chosen settings
    I2C_bus.write_i2c_block_data(
        i2c_7bit_address, PARTICLE_SENSOR_SELECT_REG, [PARTICLE_SENSOR]
    )
    I2C_bus.write_i2c_block_data(
        i2c_7bit_address, CYCLE_TIME_PERIOD_REG, [CYCLE_PERIOD]
    )

    #########################################################

    log.info("metriful publish: starting in cycle mode and waiting for data")

    I2C_bus.write_byte(i2c_7bit_address, CYCLE_MODE_CMD)

    while True:
        # Wait for the next new data release, indicated by a falling edge on READY
        while not GPIO.event_detected(READY_pin):
            sleep(0.05)

        # Now read and print all data
        read(client, I2C_bus)
