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
from solarcalc.calculations import get_combined_data, get_solar_data, get_combined_data_with_export_import, calculate_solar_totals, make_financial_projection

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {"csv"}
REQUIRED_ESB_COLUMNS = {"Read Value", "Read Type", "Read Date and End Time"}

def esb_file_exists(hash_id):
    esb_file_path = os.path.join(UPLOAD_FOLDER, hash_id + ".csv")
    return os.path.exists(esb_file_path)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = flask.Flask(__name__)
app.secret_key =b'\xd8\xf1\xb1\xaa\xeaV0\xee\x95\xb5^\xed.\x97\xf0m\\w\xc9B\xc4~\xaa\xe3'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/favicon.ico")
def favicon():
    return "Not Found", 404

@app.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "POST":

        # Getting and storing all the inputs inputted on index.html
        eircode = flask.request.form.get("eircode")   
        try:
            lat_lon = get_lat_lon_from_eircode(eircode)
        except ValueError:
            # Invalid eircode, redirect back to index
            flask.flash("Invalid Eircode. Please try again.")
            return flask.redirect(flask.url_for("index"))
        
        lat_lon_string = ",".join(map(str, lat_lon))

        # Save all these inputs to the solcalc.db database
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("INSERT INTO simulation (eircode , latitude_longitude) VALUES (?,?)", (eircode, lat_lon_string))
        last_row_id = cur.lastrowid
        # insert default values for the rest of the columns
        cur.execute("UPDATE simulation SET rated_power_per_panel = ?, number_of_panels = ?, panel_tilt = ?, panel_azimuth = ?, installation_costs = ?, import_tarriff = ?, export_tarriff = ?, interest_rate = ? WHERE id = ?", (435, 10, 35, 180, 6500, 0.25, 0.15, 5, cur.lastrowid))
        
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
        # if they are None, set them to default values
        if rated_power_per_panel is not None:
            rated_power_per_panel = int(rated_power_per_panel)
        else:
            rated_power_per_panel = 435
        if panel_azimuth is not None:
            panel_azimuth = int(panel_azimuth)
        else:
            panel_azimuth = 180
        if panel_tilt is not None:
            panel_tilt = int(panel_tilt)
        else:
            panel_tilt = 40

        if number_of_panels is None:
            number_of_panels = 10
        if installation_costs is  None:
            installation_costs = 6500
        if import_tarriff is  None:
            import_tarriff = 0.25
        if export_tarriff is  None:
            export_tarriff = 0.15
        if interest_rate is  None:
            interest_rate = 5
        #esb_file_path = os.path.join(app.config["UPLOAD_FOLDER"], hash_id + ".csv")
        #esb_file_exists = os.path.exists(esb_file_path)
        print(row)
        if row is not None:
            return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panel=rated_power_per_panel, number_of_panels=number_of_panels, panel_tilt=panel_tilt, panel_azimuth=panel_azimuth, installation_costs=installation_costs, import_tarriff=import_tarriff, export_tarriff=export_tarriff, interest_rate=interest_rate, esb_file_exists=esb_file_exists(hash_id))
        else:
            # initial default values:
            return flask.render_template("furtherdetails.html", hash_id=hash_id, rated_power_per_panel=435, number_of_panels=10, panel_azimuth=180, panel_tilt=40, installation_costs=8500, import_tarriff=0.25, export_tarriff=0.15, interest_rate=0.05, esb_file_exists=esb_file_exists(hash_id))
    else:
        raise

@app.route("/<hash_id>/financial_projections")
def financial_projections(hash_id):
    if esb_file_exists(hash_id) == False:
        return flask.render_template("financial_projections.html", hash_id=hash_id, esb_file_exists=False)
    decoded_id = decode_id(hash_id)
    con = db_get_connection()
    cur = con.cursor()
    cur.execute("SELECT rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate FROM simulation WHERE id = ?", (decoded_id,))
    row = cur.fetchone()
    con.close()



    rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, installation_costs, import_tarriff, export_tarriff, interest_rate = row

    df_comb = get_combined_data_with_export_import(hash_id, pandas.Timestamp("2024-01-01 00:00:00").tz_localize("UTC"), pandas.Timestamp("2024-12-31 23:59:59").tz_localize("UTC"))
    total_kwh_solar_used, total_kwh_export = calculate_solar_totals(df_comb)

    # do calculations and return results as a table
    df_projection = make_financial_projection(total_kwh_solar_used, total_kwh_export, installation_costs, import_tarriff, export_tarriff, interest_rate)
    df_projection["Cum. Solar Savings"] = df_projection["Cum. Solar Savings"].apply(lambda x: "{:,.2f}".format(x))
    df_projection["Cum. Export Revenue"] = df_projection["Cum. Export Revenue"].apply(lambda x: "{:,.2f}".format(x))
    df_projection["Alt. Investment Value"] = df_projection["Alt. Investment Value"].apply(lambda x: "{:,.2f}".format(x))
    df_projection["Cap Value"] = df_projection["Cap Value"].apply(lambda x: "{:,.2f}".format(x))
    df_projection["Net Position"] = df_projection["Net Position"].apply(lambda x: "{:,.2f}".format(x))

    table_html = df_projection.to_html(classes="table table-bordered table-striped", index=True, justify="center", border=0, col_space=100)
    return flask.render_template("financial_projections.html", hash_id=hash_id, rated_power_per_panel=rated_power_per_panel, number_of_panels=number_of_panels, panel_tilt=panel_tilt, panel_azimuth=panel_azimuth, installation_costs=installation_costs, import_tarriff=import_tarriff, export_tarriff=export_tarriff, interest_rate=interest_rate, total_kwh_solar_used=int(total_kwh_solar_used), total_kwh_export=int(total_kwh_export), table=table_html, esb_file_exists=True)


@app.route("/<hash_id>/process", methods=["GET", "POST"])
def process_esb(hash_id):
    if flask.request.method == "POST":
        file = flask.request.files.get("esb_file")

        # No file part in the request
        if not file:
            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))

        if file.filename == "":
            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Try to read the file
            try:
                df = pandas.read_csv(file)
            except Exception:
                return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
            # Validate expected columns
            expected_columns = {"Read Value", "Read Type", "Read Date and End Time"}
            if not expected_columns.issubset(df.columns):
                return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))

            file.stream.seek(0)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], hash_id + ".csv"))

            return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
        return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))
    return flask.redirect(flask.url_for("get_detailed_user_data", hash_id=hash_id))


@app.route("/<hash_id>/simulate")
def simulate(hash_id):
    return flask.render_template("simulator.html", hash_id=hash_id, esb_file_exists=esb_file_exists(hash_id))


@app.route("/<hash_id>/simulate_excess_energy")
def simulate_excess_energy(hash_id):
    return flask.render_template("simulate_excess_energy.html", hash_id=hash_id, esb_file_exists=esb_file_exists(hash_id))

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
        monthly_power_excess = combined_data_by_month["power_export"].sum() * .001 * .5
        monthly_power_import = combined_data_by_month["power_import"].sum() * .001 * .5
        data.append({"month": MONTHS[i-1], "power_export": monthly_power_excess, "power_import": monthly_power_import})

    return json.dumps(data)