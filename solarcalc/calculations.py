import pandas
import numpy
import pvlib

# Function that calculates power output of a solar panel 
# Makes assumptions about weather
# date and time not constant for this project
def calc_power_output(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth):    
    location = pvlib.location.Location(latitude, longitude)
    #clearsky_irradiance =  location.get_clearsky(times)

    # Typical meteorogical year using the pvgis api
    data, _, _, _ = pvlib.iotools.get_pvgis_tmy(latitude=latitude, longitude=longitude)

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

def get_30min_calc_vals(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth):
    dc_power_output = calc_power_output(latitude, longitude, rated_power_per_panel, number_of_panels, panel_tilt, panel_azimuth)
    dc_power_output = dc_power_output.reset_index().rename(columns={"time(UTC)": "x", 0: "y"})

    times = pandas.date_range(start="2024-01-01 00:30:00.000", end="2024-12-31 00:00:00.000", freq="1h", tz="UTC")

    new_rows = pandas.DataFrame({"x": times, "y": numpy.nan})
        
    dc_power_output = pandas.concat([dc_power_output, new_rows], ignore_index=True)

    dc_power_output = dc_power_output.sort_values(by="x").reset_index(drop=True)

    if numpy.isnan(dc_power_output.loc[0, "y"]):
        dc_power_output.loc[0, "y"] = 0

    if numpy.isnan(dc_power_output.loc[len(dc_power_output) - 1, "y"]):
        dc_power_output.loc[len(dc_power_output) - 1, "y"] = 0

    dc_power_output["y"] = get_avg_value(dc_power_output["y"].to_list())
    return dc_power_output

def get_avg_value(values):
    values = numpy.array(values)
    for i in range(1, len(values)):
        if numpy.isnan(values[i]):
            values[i] = (values[i-1] + values[i+1]) / 2
    return values

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