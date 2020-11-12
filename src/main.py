from flask import Flask, jsonify, request

app = Flask("zd-mailbot")
application = app # Heroku seems to really want this


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/jsondata")
def jsondata():
    return jsonify({"name": "duncan"}), 200


@app.route("/test", methods=['GET', 'POST'])
def test_get():
    if request.method == 'GET':
        return jsonify({"job": "good"}), 200
    elif request.method == 'POST':
        print(">>>>", request.get_json())
        return request.get_json()



@app.route("/consult.json", methods=['GET'])
def notify_consultant():
    print(request)
    return jsonify({"job": "good"}), 200


if __name__ == "__main__":
    app.run(debug=True)

