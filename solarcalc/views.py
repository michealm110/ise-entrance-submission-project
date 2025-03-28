
import flask
from random import randrange

app = flask.Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "POST":
        eircode = flask.request.form.get('eircode', '')   
        return flask.render_template('index.html', eircode=eircode) #this isnt actually want   
    elif flask.request.method == "GET":
        return flask.render_template('index.html')
    else:
        #boom!
        raise


def make_random_name() -> str:
    # 8 charachters [a-z0-9]

    #using ascii and randrange
    #Three sections; 0-9 (10/62), A-Z (26/62), a-z(26/62)
    x = ""
    for i in range(8):
        num = randrange(0,36)
        char = 0
        if 0 <= num <= 9:
            char = 48 + num
        elif 10 <= num <= 35:
            char = 97 + (num - 10)
        x += chr(char)
    return x
