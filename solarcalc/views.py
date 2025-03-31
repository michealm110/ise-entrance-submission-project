
import flask
import sqlite3
import hashids
import requests
import pvlib
import pandas
from datetime import datetime, timedelta, timezone
import pytz

def db_get_connection():

    con = sqlite3.connect('solarcalc.db')
    con.execute("CREATE TABLE IF NOT EXISTS simulation (id INTEGER PRIMARY KEY AUTOINCREMENT, eircode TEXT NOT NULL , latitude_longitude TEXT, panel_area REAL, panel_efficiency REAL, panel_tilt REAL, panel_azimuth REAL);")
    con.commit()
    return con

app = flask.Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "POST":

        # Getting and storing all the inputs inputted on index.html
        eircode = flask.request.form.get('eircode')   
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
        return flask.redirect(flask.url_for("show_data", hash_id=hash_id))

    elif flask.request.method == "GET":
        return flask.render_template('index.html')
    else:
        #boom!
        raise


@app.route("/<hash_id>", methods=["GET", "POST"])
def get_detailed_user_data(hash_id):
    if flask.request.method == "POST":
        decoded_id = decode_id(hash_id)
        panel_area = flask.request.form.get('panel_area')
        panel_efficiency = int(flask.request.form.get('panel_efficiency')) / 100
        panel_tilt = flask.request.form.get('panel_tilt')
        panel_azimuth = flask.request.form.get('panel_azimuth')


        # Update data base with new inputs
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("UPDATE simulation SET panel_area = ?, panel_efficiency = ?, panel_tilt = ?, panel_azimuth = ? WHERE id = ?", (panel_area, panel_efficiency, panel_tilt, panel_azimuth, decoded_id))   
        con.commit()
        con.close()
    elif flask.request.method =="GET":
        return flask.render_template("furtherdetails.html", hash_id=hash_id)
    
@app.route("/<hash_id>/solardata")
def get_json_data(hash_id):
    decoded_id = decode_id(hash_id)
    times_from_now = rounds_and_calculates_a_year_of_dates()
    # Get data from solarcalc.db database and plug the data into calc_power_output() 
    con = db_get_connection()
    cur = con.cursor()
    # Not worth individually assiging each parameter grabbing them all as a tuple
    cur.execute("SELECT * FROM simulation WHERE id = ?", (decoded_id,))
    decoded_id_row_from_db = cur.fetchone()
    con.close()

    # Converting the latitude_longitude to a tuple
    lat_lon = tuple(map(float, decoded_id_row_from_db[2].split(",")))

    dc_power_output = calc_power_output(lat_lon[0], lat_lon[1], decoded_id_row_from_db[3], decoded_id_row_from_db[4], decoded_id_row_from_db[5], decoded_id_row_from_db[6], times_from_now)
    dc_power_output = dc_power_output.reset_index().rename(columns={"time(UTC)": "x", 0: "y"})
    json_power_output = dc_power_output.to_json(orient="records", date_format="iso")
    return json_power_output

    
@app.route("/<hash_id>/simulate")
def simulate(hash_id):
    decoded_id = decode_id(hash_id)
    times_from_now = rounds_and_calculates_a_year_of_dates()
    # Get data from solarcalc.db database and plug the data into calc_power_output() 
    con = db_get_connection()
    cur = con.cursor()
    # Not worth individually assiging each parameter grabbing them all as a tuple
    cur.execute("SELECT * FROM simulation WHERE id = ?", (decoded_id,))
    decoded_id_row_from_db = cur.fetchone()
    con.close()

    # Converting the latitude_longitude to a tuple
    lat_lon = tuple(map(float, decoded_id_row_from_db[2].split(",")))

    dc_power_output = calc_power_output(lat_lon[0], lat_lon[1], decoded_id_row_from_db[3], decoded_id_row_from_db[4], decoded_id_row_from_db[5], decoded_id_row_from_db[6], times_from_now)
    dc_power_output = dc_power_output.reset_index().rename(columns={"time(UTC)": "x", 0: "y"})
    dc_power_output = dc_power_output.to_json("solarcalc/static/data.json", orient="records", date_format="iso")

    return flask.render_template("simulator.html", power_output=dc_power_output, hash_id=hash_id)


ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'

def encode_id(n: int) -> str:
    #salt, hash it, base36 it
    hash_encoder = hashids.Hashids(salt='this is my salt', min_length=8, alphabet=ALPHABET)
    hashid = hash_encoder.encode(n)
    return hashid

def decode_id(hash_id: str) -> int:
    hash_encoder = hashids.Hashids(salt='this is my salt', min_length=8, alphabet=ALPHABET)
    n = hash_encoder.decode(hash_id)[0]
    return n


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
    
# Function that calculates power output of a solar panel 
# Makes assumptions about weather
# date and time not constant for this project
def calc_power_output(latitude, longitude, panel_area, panel_efficiency, panel_tilt, panel_azimuth, times):
    tz = 'Europe/Dublin'
    location = pvlib.location.Location(latitude, longitude)
    #clearsky_irradiance =  location.get_clearsky(times)

    data, _, _ , _ = pvlib.iotools.get_pvgis_tmy(latitude=latitude, longitude=longitude)

    solar_position = location.get_solarposition(data.index)


    # solar_position = location.get_solarposition(date_time)
    # Optimisic estimate of solar irradiation because it assumes clear skies
    # clear_sky = location.get_clearsky(date_time, model="ineichen")
    irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel_tilt,
        surface_azimuth=panel_azimuth,
        solar_zenith=solar_position['zenith'],
        solar_azimuth=solar_position['azimuth'],
        ghi=data['ghi'],
        dni=data['dni'],
        dhi=data['dhi'])
    
    # default values entered for wind_speed, u0, and u1
    module_temperature = pvlib.temperature.faiman(poa_global=irradiance["poa_global"], temp_air=data["temp_air"], wind_speed=1, u0=25.0, u1=6.84)

    dc_power = pvlib.pvsystem.pvwatts_dc(
    g_poa_effective=irradiance['poa_global'],
    # simplified assumptions that module and cell temperature are the same
    temp_cell=module_temperature,
    pdc0=300,
    gamma_pdc=-0.004,
    temp_ref=25.0,
    )

    dc_power.index = dc_power.index.map(lambda x: x.replace(year=2024))



    # Returns power output of your solar panel in Watts at a specific location
    return dc_power

def rounds_and_calculates_a_year_of_dates():
    tz = "Europe/Dublin"
    #times = pd.date_range(start='2025-03-29 00:00:00', end='2025-03-30 00:00:00', freq='30min', tz='Europe/Dublin')
    tz_formatted = pytz.timezone(tz)
    time_now_aware = datetime.now(tz_formatted)
    delta = timedelta(minutes=30)
    time_rounded_down = time_now_aware - (time_now_aware - datetime.min.replace(tzinfo=timezone.utc)) % delta
    return pandas.date_range(start=time_rounded_down.replace(year=(int(time_rounded_down.year) - 1)), end=time_rounded_down, freq="30min", tz=tz)

