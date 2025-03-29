
import flask
import sqlite3
from random import randrange
import hashids
import requests

def db_get_connection():

    con = sqlite3.connect('solarcalc.db')
    con.execute("CREATE TABLE IF NOT EXISTS simulation (id INTEGER PRIMARY KEY AUTOINCREMENT, eircode TEXT NOT NULL , latitude_longitude TEXT);")
    con.commit()
    return con

app = flask.Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "POST":
        eircode = flask.request.form.get('eircode', '')   
        lat_lon = get_lat_lon_from_eircode(eircode)
        lat_lon_string = ",".join(map(str, lat_lon))
        con = db_get_connection()
        cur = con.cursor()
        cur.execute("INSERT INTO simulation (eircode , latitude_longitude) VALUES (?,?)", (eircode, lat_lon_string))
        last_row_id = cur.lastrowid
        con.commit()
        con.close()
        hash_id = make_random_name(last_row_id)
        #return flask.render_template('index.html', eircode=hash_id)
        return flask.redirect(flask.url_for("show_data", hash_id=hash_id))

    elif flask.request.method == "GET":
        return flask.render_template('index.html')
    else:
        #boom!
        raise
    
@app.route("/<hash_id>")
def show_data(hash_id):
    return flask.render_template("displayhashid.html", hash_id=hash_id)

def make_random_name(n: int) -> str:
    '''
        # 8 charachters [a-z0-9]
    # using ascii and randrange
    # two sections; 0-9 (10/36),a-z(26/36)
    x = ""
    for i in range(8):
        num = randrange(0,36)
        char = 0
        if 0 <= num <= 9:
            char = 48 + num
        elif 10 <= num <= 35:
            char = 97 + (num - 10)
        x += chr(char)
    #salt, hash it, base36 it
    '''
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    hash_encoder = hashids.Hashids(salt='this is my salt', min_length=8, alphabet=alphabet)
    hashid = hash_encoder.encode(n)

    return hashid



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

