# import spotify as sp
import subprocess
from logger import log
from flora import flora_page, flora_frame
from energy import energy_page
from mqtt import Mqtt
import json, time, os
from flask import Flask, render_template, request
from ping3 import ping


###############################################
# Confifg
###############################################
SERVICES = [
    "climate",
    "hives",
    "environmentals",
    "electricity_meter",
    "fauxmo",
    "flora_persists",
    "ghome",
    "grafana-server",
    "influxdb",
    "nginx",
    "metriful",
    "mosquitto",
    "site",
    "temperature",
]
KEF_IP = os.getenv('KEF_IP', '192.168.1.30')
LOG_DIR = os.getenv('LOG_DIR', '/mnt/spiderdrive/logs/')


mqtt = Mqtt()

app = Flask(__name__)
# CORS(app)


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/services", methods=["GET"])
def services_state():
    status = {}
    for service in SERVICES:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                capture_output=True,
                timeout=5,
            )
            status[service] = result.returncode == 0
        except subprocess.TimeoutExpired:
            status[service] = False
        except Exception as e:
            log.error(f"Failed to check service {service}: {e}")
            status[service] = False
    return json.dumps(status)


@app.route("/flora")
def flora():
    return flora_page()


@app.route("/energy")
def energy():
    return energy_page()


@app.route("/sensors/arduino", methods=["GET"])
def sensors():
    return render_template("diy-sensors.html")


@app.route("/logs", methods=["GET"])
def logs():
    return render_template("logs.html")


@app.route("/logs/<file>", methods=["GET"])
def file_log(file):
    filename = os.path.basename(file)
    path = os.path.realpath(os.path.join(LOG_DIR, f"{filename}.log"))
    if not (
        path.startswith(os.path.realpath(LOG_DIR) + os.sep) and os.path.isfile(path)
    ):
        # pass file into the template so the js will call logs_stream with the argument
        return render_template("logs.html", file=file)
    else:
        return render_template("logs.html")


@app.route("/logs/stream/<file>", methods=["GET"])
def logs_stream(file):
    filename = os.path.basename(file)
    path = os.path.realpath(os.path.join(LOG_DIR, f"{filename}.log"))
    if not (
        path.startswith(os.path.realpath(LOG_DIR) + os.sep) and os.path.isfile(path)
    ):

        def generate(filename):
            try:
                with open(filename) as f:
                    while True:
                        yield f.read()
                        time.sleep(1)
            except Exception as e:
                log.error(f"failed to open log file: {file}", exc_info=e)
                return "you nosy bastard", 400

        return app.response_class(generate(filename), mimetype="text/plain")
    else:
        log.warning(
            f"some sneaky one try to access log: {file} [ip={request.remote_addr}]"
        )
        return "you nosy bastard", 400


@app.route('/kef', methods=['GET'])
def kef_state():
    result = ping(KEF_IP)
    on = result is not None
    if result is not None:
        log.info(f"speaker is reachable, time: {result} ms")

    info = {
        'on': on
    }

    return json.dumps(info), 200

@app.route("/execute/<device>/<command>", methods=["POST"])
def execute_command(device, command):
    data = request.get_json()

    log.info(f"execute for device 'device': '{data}'")

    if data == None:
        return json.dumps({"message": "failed to understand request"}), 400

    return mqtt.execute(device, command, data)


@app.route("/frame/<frame>")
def frame(frame):
    if frame == "flora":
        arg = request.args.get("theme")
        theme = "light" if arg != None and arg.lower() == "light" else "dark"
        return flora_frame(theme)
    else:
        return render_template("404.html"), 404


@app.errorhandler(403)
def page_forbidden(e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True, debug=False)
