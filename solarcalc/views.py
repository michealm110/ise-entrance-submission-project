import flask
import pvlib
import pandas
from datetime import datetime, timedelta, timezone
import pytz
import os
from werkzeug.utils import secure_filename
import numpy
import json

from solarcalc.database import encode_id, decode_id, db_get_connection, get_lat_lon_from_eircode
from solarcalc.calculations import get_combined_data, get_solar_data, get_combined_data_with_export_import

UPLOAD_FOLDER = "/Users/michealmcmagh/Desktop/ise-entrance-submission-project/solarcalc/uploads"
ALLOWED_EXTENSIONS = {"csv"}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = flask.Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "POST":

        # Getting and storing all the inputs inputted on index.html
        eircode = flask.request.form.get("eircode")   
        lat_lon = get_lat_lon_from_eircode(eircode)
        lat_lon_string = ",".join(map(str, lat_lon))

        # Save all these inputs to the solcalc.db database
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("INSERT INTO simulation (eircode , latitude_longitude) VALUES (?,?)", (eircode, lat_lon_string))
        last_row_id = cur.lastrowid
        con.commit()
        con.close()

        hash_id = encode_id(last_row_id)
        return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))

    elif flask.request.method == "GET":
        return flask.render_template("index.html")
    else:
        raise

@app.route("/<hash_id>", methods=["GET", "POST"])
def get_detailed_user_data(hash_id):
    decoded_id = decode_id(hash_id)
    if flask.request.method == "POST":
        rated_power_per_panel = flask.request.form.get("rated_power_per_panel")
        number_of_panels = flask.request.form.get("number_of_panels")
        panel_tilt = flask.request.form.get("panel_tilt")
        panel_azimuth = flask.request.form.get("panel_azimuth")
        installation_costs = flask.request.form.get("installation_costs")
        import_tarriff = flask.request.form.get("import_tarriff")
        export_tarriff = flask.request.form.get("export_tarriff")
        interest_rate = flask.request.form.get("interest_rate")


        # Update data base with new inputs
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("UPDATE simulation SET rated_power_per_panel = ?, number_of_panels = ?, panel_tilt = ?, panel_azimuth = ?, installation_costs = ?, import_tarriff = ?, export_tarriff = ?, interest_rate = ? WHERE id = ?", (rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate, decoded_id))
        con.commit()
        con.close()

        return flask.render_template("furtherdetails.html", hash_id=hash_id,  rated_power_per_panel=rated_power_per_panel, number_of_panels=number_of_panels, panel_azimuth=panel_azimuth, panel_tilt=panel_tilt, installation_costs=installation_costs, import_tarriff=import_tarriff, export_tarriff=export_tarriff, interest_rate=interest_rate)
    elif flask.request.method == "GET":
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("SELECT rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate FROM simulation WHERE id = ?", (decoded_id,))
        row = cur.fetchone()
        # row is a tuple or "None"
        con.close()
        rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate = row
        # some of these need to be rounded as i made them floats in the database
        rated_power_per_panel = int(rated_power_per_panel)
        panel_azimuth = int(panel_azimuth)
        panel_tilt = int(panel_tilt)

        print(row)
        if row is not None:
            return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panel=rated_power_per_panel, number_of_panels=number_of_panels, panel_tilt=panel_tilt, panel_azimuth=panel_azimuth, installation_costs=installation_costs, import_tarriff=import_tarriff, export_tarriff=export_tarriff, interest_rate=interest_rate)
        else:
            # initial default values:
            return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panel=445, number_of_panels=4, panel_azimuth=180, panel_tilt=40, installation_costs=8500, import_tarriff=0.25, export_tarriff=0.15, interest_rate=0.05)
    else:
        raise

@app.route("/<hash_id>/financial_projections")
def get_financial_projections(hash_id):
    decoded_id = decode_id(hash_id)
    con = db_get_connection()
    cur = con.cursor()
    cur.execute("SELECT rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate FROM simulation WHERE id = ?", (decoded_id,))
    row = cur.fetchone()
    con.close()
    rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, cost_per_panel, maintenance_cost_per_year, electricity_rate, efficiency_degradation = row
    total_cost = installation_costs + (cost_per_panel * number_of_panels)

    # do calculations and return results as a table


@app.route("/<hash_id>/process", methods=["GET", "POST"])
def process_esb(hash_id):
    if flask.request.method == "POST":

        # Check if the post request has the file part
        if "esb_file" not in flask.request.files:
            # back to details
            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
        file = flask.request.files["esb_file"]
        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == "":
            # Invalid back to details
            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            file.save(os.path.join(app.config["UPLOAD_FOLDER"], hash_id + ".csv"))
            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
    # No valid file redirect
    return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))

@app.route("/<hash_id>/simulate")
def simulate(hash_id):
    return flask.render_template("simulator.html", hash_id=hash_id)

@app.route("/<hash_id>/simulate_excess_energy")
def simulate_excess_energy(hash_id):
    return flask.render_template("simulate_excess_energy.html", hash_id=hash_id)

# JSON Views ###############################################################

@app.route("/<hash_id>/combineddata", methods=["GET"])
def get_combined_json_data_for_simulator(hash_id):
    start = flask.request.args.get("start", "2024-")
    start = pandas.to_datetime(start).tz_localize("UTC")
    end = start + pandas.Timedelta(hours=23, minutes=30)

    combined_data = get_combined_data(hash_id, start, end)

    return combined_data.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/energy_needed_to_import")
def get_energy_needed_json_data(hash_id):
    start = flask.request.args.get("start", "2024-")
    start = pandas.to_datetime(start).tz_localize("UTC")
    end = start + pandas.Timedelta(hours=23, minutes=30)

    combined_data = get_combined_data_with_export_import(hash_id, start, end)
    combined_data = combined_data.drop(columns=["power_solar", "power_esb"])
    return combined_data.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/excess_solar_energy") 
def get_excess_solar_json_data(hash_id):
    start = flask.request.args.get("start", "2024-")
    start = pandas.to_datetime(start).tz_localize("UTC")
    end = start + pandas.Timedelta(hours=23, minutes=30)

    combined_data = get_combined_data_with_export_import(hash_id, start, end)
    combined_data = combined_data.drop(columns=["power_solar", "power_esb"])
    return combined_data.to_json(orient="records", date_format="iso")

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
)

@app.route("/<hash_id>/import_and_export_data")
def get_import_and_export_json_data(hash_id):
    start = pandas.Timestamp("2024-01-01 00:00:00").tz_localize("UTC")
    end = pandas.Timestamp("2024-12-31 23:59:59").tz_localize("UTC")
    combined_data = get_combined_data_with_export_import(hash_id, start, end)

    # Calculate monthly totals
    data = []

    # need to convert from power to energy
    for i in range(1,13):
        combined_data_by_month = combined_data[combined_data["datetime"].dt.month == i]
        monthly_power_excess = combined_data_by_month["power_export"].sum()
        monthly_power_import = combined_data_by_month["power_import"].sum()
        data.append({"month": MONTHS[i-1], "power_export": monthly_power_excess, "power_import": monthly_power_import})

    return json.dumps(data)