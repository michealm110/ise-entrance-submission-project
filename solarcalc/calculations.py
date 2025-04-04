import pandas
import numpy
import pvlib

from solarcalc.database import db_get_connection, decode_id


# Function that calculates power output of a solar panel 
# Makes assumptions about weather
# date and time not constant for this project
def calc_power_output(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, start, end):    
    location = pvlib.location.Location(latitude, longitude)
    #clearsky_irradiance =  location.get_clearsky(times)

    # Typical meteorogical year using the pvgis api
    data, _, _, _ = pvlib.iotools.get_pvgis_tmy(latitude=latitude, longitude=longitude, coerce_year=2024)
    data = data[(data.index >= start) & (data.index <= end)]
    solar_position = location.get_solarposition(data.index)

    #solar_position = location.get_solarposition(date_time)
    # Optimisic estimate of solar irradiation because it assumes clear skies
    # clear_sky = location.get_clearsky(date_time, model="ineichen")

    # Calculates the irradiance watts per m squared of the panel surface
    # Pvlib assumes a gorund albedo of around .2 which is correspondant with grass and soil, may differ for highly reflective surfaces like snow
    irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel_tilt,
        surface_azimuth=panel_azimuth,
        solar_zenith=solar_position['zenith'],
        solar_azimuth=solar_position['azimuth'],
        ghi=data['ghi'],
        dni=data['dni'],
        dhi=data['dhi'])
    
    #default values entered for wind_speed, u0, and u1
    module_temperature = pvlib.temperature.faiman(poa_global=irradiance["poa_global"], temp_air=data["temp_air"], wind_speed=1, u0=25.0, u1=6.84)

    dc_power = pvlib.pvsystem.pvwatts_dc(
    g_poa_effective=irradiance['poa_global'],
    # simplified assumptions that module and cell temperature are the same
    temp_cell=module_temperature,
    pdc0=rated_power_per_panel,
    gamma_pdc=-0.004,
    temp_ref=25.0,
    )
    #dc_power.index = dc_power.index.replace(year=2024)
    dc_power.index = dc_power.index.map(lambda x: x.replace(year=2024))

    # Plot x-axis: time, y-axis: dc_power on a line chart thingy
    #matplotlib.pyplot.plot
    

    return dc_power * number_of_panels

def get_30min_calc_vals(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, start, end):
    if start.year !=  end.year:
        raise ValueError("Start and end dates must be in the same year.")
    if start >= end:
        raise ValueError("Start date must be before end date.")
    
    dc_power_output = calc_power_output(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, start, end)
    dc_power_output = dc_power_output.reset_index().rename(columns={"time(UTC)": "datetime", 0: "power"})

    act_start = start.replace(year=2024, minute=30)
    act_end = end.replace(year=2024)

    times = pandas.date_range(start=act_start, end=act_end, freq="1h", tz="UTC")

    new_rows = pandas.DataFrame({"datetime": times, "power": numpy.nan})
        
    dc_power_output = pandas.concat([dc_power_output, new_rows], ignore_index=True)

    dc_power_output = dc_power_output.sort_values(by="datetime").reset_index(drop=True)

    if numpy.isnan(dc_power_output.loc[0, "power"]):
        dc_power_output.loc[0, "power"] = 0

    if numpy.isnan(dc_power_output.loc[len(dc_power_output) - 1, "power"]):
        dc_power_output.loc[len(dc_power_output) - 1, "power"] = 0

    dc_power_output["power"] = get_avg_value(dc_power_output["power"].to_list())
    return dc_power_output

def get_avg_value(values):
    values = numpy.array(values)
    for i in range(1, len(values)):
        if numpy.isnan(values[i]):
            values[i] = (values[i-1] + values[i+1]) / 2
    return values

def get_esb_data(hash_id, start, end):
    esb_intake = pandas.read_csv(f"/Users/michealmcmagh/Desktop/ise-entrance-submission-project/solarcalc/uploads/{hash_id}.csv")
    esb_intake = pandas.concat([esb_intake["Read Date and End Time"], esb_intake["Read Value"]], join="inner", axis=1)
    esb_intake = esb_intake.rename(columns={"Read Date and End Time": "datetime", "Read Value": "power"})
    # Converts killowatts to watts
    esb_intake["power"] = esb_intake["power"] * 1000
    esb_intake["datetime"] = pandas.to_datetime(esb_intake["datetime"], dayfirst=True).dt.tz_localize('UTC')
    esb_intake = esb_intake.sort_values(by=['datetime'])
    esb_intake = esb_intake[(esb_intake["datetime"] >= start) & (esb_intake["datetime"] <= end)]
    return esb_intake


'''
# This function was misinformed in its creation going to keep it in until i figure out if its completely misguided or not
def rounds_and_calculates_a_year_of_dates():
    tz = "Europe/Dublin"
    #times = pd.date_range(start="2025-03-29 00:00:00", end="2025-03-30 00:00:00", freq="30min", tz="Europe/Dublin")
    tz_formatted = pytz.timezone(tz)
    time_now_aware = datetime.now(tz_formatted)
    delta = timedelta(minutes=30)
    time_rounded_down = time_now_aware - (time_now_aware - datetime.min.replace(tzinfo=timezone.utc)) % delta
    return pandas.date_range(start=time_rounded_down.replace(year=(int(time_rounded_down.year) - 1)), end=time_rounded_down, freq="30min", tz=tz)'
'''


def get_solar_data(hash_id, start, end):
    decoded_id = decode_id(hash_id)
    # times_from_now = rounds_and_calculates_a_year_of_dates()
    # Get data from solarcalc.db database and plug the data into calc_power_output() 
    con = db_get_connection()
    cur = con.cursor()
    # Not worth individually assiging each parameter grabbing them all as a tuple
    cur.execute("SELECT id, eircode, latitude_longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth FROM simulation WHERE id = ?", (decoded_id,))
    decoded_id_row_from_db = cur.fetchone()
    con.close()

    #TODO: if id is not in database do somehting more sensible

    _, _, lat_long, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth = decoded_id_row_from_db
    latitude, longitude = tuple(map(float, lat_long.split(",")))

    dc_power_output = get_30min_calc_vals( latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth, start, end)

    return dc_power_output


def get_combined_data(hash_id, start, end):
    solar_data =  get_solar_data(hash_id, start, end)
    esb_data = get_esb_data(hash_id, start, end)

    solar_data = solar_data[(solar_data["datetime"] >= start) & (solar_data["datetime"] <= end)]
    esb_data = esb_data[(esb_data["datetime"] >= start) & (esb_data["datetime"] <= end)]
    combined_data = pandas.merge(solar_data.rename(columns={"power": "power_solar"}), esb_data.rename(columns={"power": "power_esb"}), on="datetime", how="outer")

    return combined_data

def get_combined_data_with_export_import(hash_id, start, end):
    combined_data = get_combined_data(hash_id, start, end)

    combined_data["power_export"] = combined_data["power_solar"] - combined_data["power_esb"]
    combined_data.loc[combined_data["power_export"] < 0, "power_export"] = 0

    combined_data["power_import"] = combined_data["power_esb"] - combined_data["power_solar"]
    combined_data.loc[combined_data["power_import"] < 0, "power_import"] = 0

    combined_data["used_solar_power"] = combined_data["power_solar"] - combined_data["power_export"]
    combined_data.loc[combined_data["used_solar_power"] < 0, "used_solar_power"] = 0
    return combined_data