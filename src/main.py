from flask import Flask, jsonify

app = Flask("zd-mailbot")
application = app # Heroku seems to really want this


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/jsondata")
def jsondata():
    return jsonify({"name": "duncan"}), 200


@app.route("/consult.json")
def notify_consultant():
    return jsonify({"job": "good"}), 200


if __name__ == "__main__":
    app.run(debug=True)

