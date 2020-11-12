from flask import Flask, jsonify

app = Flask("zd-mailbot")


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/jsondata")
def jsondata():
    return jsonify({"name": "duncan"}), 200


if __name__ == "__main__":
    app.run(debug=True)

