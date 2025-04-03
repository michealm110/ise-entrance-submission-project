import sqlite3
import hashids

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
    con.execute("CREATE TABLE IF NOT EXISTS simulation (id INTEGER PRIMARY KEY AUTOINCREMENT, eircode TEXT NOT NULL , latitude_longitude TEXT, rated_power_per_panel REAL, number_of_panels INTEGER, panel_tilt REAL, panel_azimuth REAL);")
    con.commit()
    return con

