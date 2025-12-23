import os
import json
import time
import subprocess
from logger import log
from flora import flora_page, flora_frame
from mqtt import Mqtt
import json, time, os
from flask import Flask, render_template, request
from ping3 import ping


###############################################
# Confifg
###############################################
SERVICES = [
    "climate",
    "energy",
    "flora",
    "ghome",
    "hives",
    "nginx",
    "metriful",
    "mosquitto",
    "site",
    "temperature",
]
KEF_IP = os.getenv("KEF_IP", "192.168.1.1")
LOG_DIR = os.getenv("LOG_DIR", "/var/log/")


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
        except OSError as e:
            log.error(f"Failed to check service {service}: {e}")
            status[service] = False
    return json.dumps(status)


@app.route("/flora")
def flora():
    return flora_page()


@app.route("/sensors/arduino", methods=["GET"])
def sensors():
    return render_template("diy-sensors.html")


@app.route("/logs", methods=["GET"])
def logs():
    return render_template("logs.html")


@app.route("/logs/<file>", methods=["GET"])
def file_log(file):
    basename = os.path.basename(file)
    filename = os.path.realpath(os.path.join(LOG_DIR, f"{basename}.log"))

    if not filename.startswith(os.path.realpath(LOG_DIR) + os.sep) or not os.path.isfile(filename):
        return render_template("logs.html")

    # pass file into the template so the js will call logs_stream with the argument
    return render_template("logs.html", file=file)


@app.route("/logs/stream/<file>", methods=["GET"])
def logs_stream(file):
    basename = os.path.basename(file)
    filename = os.path.realpath(os.path.join(LOG_DIR, f"{basename}.log"))

    if not filename.startswith(os.path.realpath(LOG_DIR) + os.sep) or not os.path.isfile(filename):
        log.warning(f"some sneaky one try to access log: {file} [ip={request.remote_addr}]")
        return "you nosy bastard", 400

    def generate(filename):
        try:
            with open(filename, encoding="utf-8") as f:
                while True:
                    yield f.read()
                    time.sleep(1)
        except (OSError, IOError) as e:
            log.error(f"failed to open log file: {file}", exc_info=e)
            return "you nosy bastard", 400

    return app.response_class(generate(filename), mimetype="text/plain")


@app.route("/kef", methods=["GET"])
def kef_state():
    result = ping(KEF_IP)
    on = result is not None
    if result is not None:
        log.info(f"speaker is reachable, time: {result} ms")

    info = {"on": on}

    return json.dumps(info), 200


@app.route("/execute/<device>/<command>", methods=["POST"])
def execute_command(device, command):
    data = request.get_json()

    log.info(f"execute for device 'device': '{data}'")

    if data is None:
        return json.dumps({"message": "failed to understand request"}), 400

    return mqtt.execute(device, command, data)


@app.route("/frame/<frame>")
def get_frame(frame):
    if frame == "flora":
        arg = request.args.get("theme")
        theme = "light" if arg is not None and arg.lower() == "light" else "dark"
        return flora_frame(theme)

    return render_template("404.html"), 404


@app.errorhandler(403)
def page_forbidden(_e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def page_not_found(_e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def page_internal_error(_e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True, debug=False)
