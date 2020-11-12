from flask import Flask, jsonify

application = Flask("zd-mailbot")


@application.route("/")
def hello_world():
    return "Hello, World!"


@application.route("/jsondata")
def jsondata():
    return jsonify({"name": "duncan"}), 200


if __name__ == "__main__":
    app.run(debug=True)

