import sqlite3
import hashids
import requests

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"

def encode_id(n: int) -> str:
    #salt, hash it, base36 it
    hash_encoder = hashids.Hashids(salt="this is my salt", min_length=8, alphabet=ALPHABET)
    hashid = hash_encoder.encode(n)
    return hashid

def decode_id(hash_id: str) -> int:
    hash_encoder = hashids.Hashids(salt="this is my salt", min_length=8, alphabet=ALPHABET)
    n = hash_encoder.decode(hash_id)[0]
    return n

def db_get_connection():
    con = sqlite3.connect("solarcalc.db")
    con.execute("CREATE TABLE IF NOT EXISTS simulation ( id INTEGER PRIMARY KEY AUTOINCREMENT, eircode TEXT NOT NULL , latitude_longitude TEXT, rated_power_per_panel REAL, number_of_panels INTEGER, panel_tilt REAL, panel_azimuth REAL, installation_costs NUMERIC, import_tarriff NUMERIC, export_tarriff NUMERIC, interest_rate NUMERIC);")
    con.commit()
    return con


import requests

def get_lat_lon_from_eircode(eircode):
    api_key = "AIzaSyA5MFJFJZCCJHbvkzL3bC-9fCqrm4BxxMM"
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": eircode,
        "region": "ie",  # Focus the search in Ireland
        "key": api_key
    }

    response = requests.get(base_url, params=params)
    response.raise_for_status()  # Raises an error for bad responses
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        raise ValueError(f"Geocoding failed: {data['status']} - {data.get('error_message', '')}")


