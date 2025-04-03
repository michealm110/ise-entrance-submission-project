import flask
import requests
import pvlib
import pandas
from datetime import datetime, timedelta, timezone
import pytz
import os
from werkzeug.utils import secure_filename
import numpy
import json

from solarcalc.database import encode_id, decode_id, db_get_connection
from solarcalc.calculations import get_30min_calc_vals

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
    if flask.request.method == "POST":
        decoded_id = decode_id(hash_id)
        rated_power_per_panel = flask.request.form.get("rated_power_per_panel")
        number_of_panels = flask.request.form.get("number_of_panels")
        panel_tilt = flask.request.form.get("panel_tilt")
        panel_azimuth = flask.request.form.get("panel_azimuth")


        # Update data base with new inputs
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("UPDATE simulation SET rated_power_per_panel = ?, number_of_panels = ?, panel_tilt = ?, panel_azimuth = ? WHERE id = ?", (rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, decoded_id))   
        con.commit()
        con.close()

        return flask.render_template("furtherdetails.html", hash_id=hash_id)
    elif flask.request.method == "GET":
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM simulation WHERE id = ?", (hash_id,))
        row = cur.fetchone()
        # row is a tuple or "None"
        con.close()

        if row is not None:
            return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panela=row[3], number_of_panelsy=row[4], panel_tilt=row[5], panel_azimuth=row[6])
        
        return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panel=445, number_of_panels=1, panel_azimuth=180, panel_tilt=18)
    else:
        raise

    
@app.route("/<hash_id>/solardata")
def get_json_data(hash_id):
    decoded_id = decode_id(hash_id)
    # times_from_now = rounds_and_calculates_a_year_of_dates()
    # Get data from solarcalc.db database and plug the data into calc_power_output() 
    con = db_get_connection()
    cur = con.cursor()
    # Not worth individually assiging each parameter grabbing them all as a tuple
    cur.execute("SELECT id, eircode, latitude_longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth FROM simulation WHERE id = ?", (decoded_id,))
    decoded_id_row_from_db = cur.fetchone()
    con.close()

    _, _, lat_long, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth = decoded_id_row_from_db
    latitude, longitude = tuple(map(float, lat_long.split(",")))

    dc_power_output = get_30min_calc_vals( latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth)

    return dc_power_output.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/esbdata")
def get_esb_json_data(hash_id):
    esb_intake = pandas.read_csv(f"/Users/michealmcmagh/Desktop/ise-entrance-submission-project/solarcalc/uploads/{hash_id}.csv")
    esb_intake = pandas.concat([esb_intake["Read Date and End Time"], esb_intake["Read Value"]], join="inner", axis=1)
    esb_intake = esb_intake.rename(columns={"Read Date and End Time": "x", "Read Value": "y"})
    # Converts killowatts to watts
    esb_intake["y"] = esb_intake["y"] * 1000
    esb_intake["x"] = pandas.to_datetime(esb_intake["x"], dayfirst=True).dt.tz_localize('UTC')
    esb_intake = esb_intake.sort_values(by=['x'])

    return esb_intake.to_json(orient='records', date_format='iso')

@app.route("/<hash_id>/full_combined_data")
def get_combined_json_data(hash_id):
    solar_json_data = get_json_data(hash_id=hash_id)
    esb_json_data = get_esb_json_data(hash_id=hash_id)
    solar_data = pandas.DataFrame.from_records(json.loads(solar_json_data))
    esb_data = pandas.DataFrame.from_records(json.loads(esb_json_data))
    solar_data["x"] = pandas.to_datetime(solar_data["x"])
    esb_data["x"] = pandas.to_datetime(esb_data["x"])
    start = pandas.Timestamp("2024-01-01 00:00:00", tz="UTC")
    end = pandas.Timestamp("2024-12-31 23:59:59", tz="UTC")
    solar_data = solar_data[(solar_data["x"] >= start) & (solar_data["x"] <= end)]
    esb_data = esb_data[(esb_data["x"] >= start) & (esb_data["x"] <= end)]
    combined_data = pandas.merge(solar_data.rename(columns={"y": "y1"}), esb_data.rename(columns={"y": "y2"}), on="x", how="outer")

    return combined_data.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/combineddata", methods=["GET"])
def get_combined_json_data_for_simulator(hash_id):
    combined_json_data = get_combined_json_data(hash_id=hash_id)
    combined_data = pandas.DataFrame.from_records(json.loads(combined_json_data))
    start = flask.request.args.get("start", "2024-")
    start = pandas.to_datetime(start).tz_localize("UTC")
    end = start + pandas.Timedelta(hours=23, minutes=30)    
    combined_data["x"] = pandas.to_datetime(combined_data["x"]) 
    combined_data = combined_data[(combined_data["x"] >= start) & (combined_data["x"] < end)]

    return combined_data.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/simulate")
def simulate(hash_id):
    return flask.render_template("simulator.html", hash_id=hash_id)

@app.route("/<hash_id>/excess_energy")   
def  get_excess_json_data(hash_id):
    combined_json_data = get_combined_json_data(hash_id=hash_id)
    combined_data = pandas.DataFrame.from_records(json.loads(combined_json_data))
    start = flask.request.args.get("start", "2024-01-01")
    start = pandas.to_datetime(start).tz_localize("UTC")
    end = start + pandas.Timedelta(hours=23, minutes=30) 
    combined_data["x"] = pandas.to_datetime(combined_data["x"]) 
    combined_data = combined_data[(combined_data["x"] >= start) & (combined_data["x"] < end)]
    if "y1" in combined_data.columns and "y2" in combined_data.columns:
        combined_data["y"] = combined_data["y2"] - combined_data["y1"]
        combined_data.loc[combined_data["y"] < 0, "y"] = 0
    else:
        combined_data["y"] = 0
    combined_data = combined_data.drop(columns=["y1", "y2"])
    return combined_data.to_json(orient="records", date_format="iso")

@app.route("/<hash_id>/simulate_excess_energy")
def simulate_excess_energy(hash_id):
    return flask.render_template("simulate_excess_energy.html", hash_id=hash_id)

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

def get_lat_lon_from_eircode(eircode):
    base_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "MickSolarCalc/1.0"} 
    params = {"q": eircode, "format": "json"}
    response = requests.get(base_url, headers=headers, params=params)
    data = response.json()

    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    else:
        return None
