import os
from datetime import datetime
from flask import render_template, Markup
from influxdb import InfluxDBClient
from dateutil import parser, tz
from logger import log


# Configure InfluxDB connection from environment variables
dbhost = os.getenv("INFLUXDB_HOST", "localhost")
dbport = int(os.getenv("INFLUXDB_PORT", "8086"))
dbuser = os.getenv("INFLUXDB_USER", "user")
dbpassword = os.getenv("INFLUXDB_PASSWORD", "")
dbname = os.getenv("INFLUXDB_FLORA_DATABASE", "flora")


def load_data(client):
    log.debug("load data from influxdb")
    results = client.query(
        "SELECT * FROM /.*/ WHERE time >= now() - 24h ORDER BY time DESC LIMIT 1"
    )
    return results


def summary(data, waterings):
    table = '<table id="data" class="flora-table tablesorter">'
    table += "<thead><tr>\
                <th>plant</th>\
                <th>temperature <i>(&deg;C)</i></th>\
                <th>moisture <i>(%)</i></th>\
                <th>conductivity <i>(µS/cm)</i></th>\
                <th>light <i>(Lux)</i></th>\
                <th>battery <i>(%)</i></th>\
                <th>watering <i>(days)</i></th>\
                <th>time</th>\
            </tr></thead>"

    for p in data.get_points():
        dt = parser.parse(p["time"]).astimezone(tz.gettz("europe/amsterdam"))
        time = dt.strftime("%H:%M")  #  %d %b")
        watering = last_watering(waterings[p["node"]])
        table += f"""<tr>
            <td>{p['node']}</td>
            <td>{p['temperature']}</td>
            <td>{p['moisture']}</td>
            <td>{p['conductivity']}</td>
            <td>{p['light']}</td>
            <td>{p['battery']}</td>
            <td>{watering}</td>
            <td>{time}</td>
        </tr>"""

    table += "</table>"

    return table


def load_waterings(client):
    log.debug("load waterings from influxdb")
    results = client.query(
        "SELECT derivative FROM (SELECT derivative(mean(moisture), 2h) FROM /.*/ WHERE time >= now()-60d and time <= now() GROUP BY time(2h)) WHERE derivative > 1.5"
    )
    return results


def watering_table(data):
    table = '<table class=" tablesorter">'
    table += "<thead><tr><th>plant</th><th>time elapsed</th><th>date</th></tr></thead>"

    for i in data.items():
        # reversed because it doesn't make sense desc returns one result
        td = ""
        for p in i[1]:
            dt = parser.parse(p["time"]).astimezone(tz.gettz("europe/amsterdam"))
            time = dt.strftime("%d %b %H:%M")
            delta = datetime.now(dt.tzinfo) - dt
            # watering = re.split(':\d{2}\.\d+', str(delta))[0]
            watering = delta.days + delta.seconds / 24 / 3600

            td = f"<tr><td>{i[0][0]}</td><td>{watering:.1f} days</td><td>{time}</td></tr>"
        table += td
    table += "</table>"

    return table


def last_watering(data):
    days = ""
    for p in data:
        dt = parser.parse(p["time"]).astimezone(tz.gettz("europe/amsterdam"))
        delta = datetime.now(dt.tzinfo) - dt
        watering = delta.days + delta.seconds / 24 / 3600
        days = f"{watering:.1f}"
    return days


def flora_page():
    try:
        client = InfluxDBClient(dbhost, dbport, dbuser, dbpassword, dbname)
        data = load_data(client)
        watering_data = load_waterings(client)

        table = summary(data, watering_data)
    except (ConnectionError, OSError, ValueError) as e:
        log.error(f"failed to load data: {e}")
        table = "<table></table>"

    return render_template("miflora.html", measurements=Markup(table))


def flora_frame(theme):
    background = "1B1B1B" if theme == "dark" else "white"
    text = "white" if theme == "dark" else "black"
    try:
        client = InfluxDBClient(dbhost, dbport, dbuser, dbpassword, dbname)
        data = load_data(client)
        watering_data = load_waterings(client)

        table = summary(data, watering_data)
    except (ConnectionError, OSError, ValueError) as e:
        log.error(f"failed to load data: {e}")
        table = "<table></table>"

    return f"""<html>
    <head>
        <meta http-equiv="refresh" content="600" /> <!-- refresh 10min -->
        <script src="/static/script/jquery.js"></script>
        <script src="/static/script/jquery.tablesorter.js"></script>
        <script>
            $(document).ready(function() {{
                $(".flora-table").tablesorter();
            }});
        </script>
        <style>
            html {{
                color: {text};
                background-color:{background};
                font-family: var(--ha-font-family-body);
                -webkit-font-smoothing: var(--ha-font-smoothing);
                font-size: var(--ha-font-size-m);
                font-weight: var(--ha-font-weight-normal);
                line-height: var(--ha-line-height-normal);
            }}
            .flora-table {{
                width: 100%;
                border-collapse: collapse;
                background: var(--card-background-color, #fff);
                color: var(--primary-text-color, #1c1c1c);
                border-radius: var(--ha-card-border-radius, 12px);
                overflow: hidden;
            }}
            .flora-table th, .flora-table td {{
                padding: 12px 16px;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
                text-align: left;
            }}
            .flora-table th {{
                background: var(--table-header-background-color, #f7f7f9);
                color: var(--primary-text-color, #1c1c1c);
                font-weight: 500;
                text-transform: none;
                letter-spacing: 0;
            }}
            .flora-table tr:last-child td {{
                border-bottom: none;
            }}
            .flora-table tr:nth-child(even) {{
                background: var(--table-row-background-color, #fafbfc);
            }}
            .flora-table tr:hover {{
                background: var(--table-row-hover-background-color, #f0f0f5);
            }}
            /* hide columns flora table if the window becomes to small-caps */
            @media only screen and (max-width: 800px) {{
            .flora-table th:nth-child(4), .flora-table td:nth-child(4),
            .flora-table th:nth-child(5), .flora-table td:nth-child(5),
            .flora-table th:nth-child(6), .flora-table td:nth-child(6) {{
                    display:none;
                }}
            }}
            .flora-table th:nth-child(n+2),
            .flora-table td:nth-child(n+2) {{
                text-align: right;
            }}
        </style>
    </head>
    <body>
        <div style=" width: 100%">
            {table}
        </div>
    </body>
    <html>"""
