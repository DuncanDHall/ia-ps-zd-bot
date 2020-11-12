from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

import smtplib
from email.message import EmailMessage

from config import *

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
        return jsonify({"good": "going!"}), 200
    elif request.method == 'POST':
        print(">>>>", request.get_json())
        return request.get_json(), 200


@app.route("/consult.json", methods=['POST'])
def consult():
    """
    payload structure:
        {
            "ticket_id": Int,
            "consultant": "<consultant>@archive.org",
            "subject": String,
            "body": String,
            "html_body": String,
        }
    :return:
    """
    try:
        json = request.get_json()
    except BadRequest as e:
        print("JSON? >> ", request.data)
        return jsonify({"Error": "Bad Request: Could not parse json object"}), 400

    try:
        message_args = (
            json['consultant'], json['subject'], json['body'],
            json['html_body'], json['ticket_id']
        )
    except KeyError as e:
        return jsonify({"Error": "Json object must contain the following non-optional keys",
                        "keys": ["consultant", "subject", "body", "html_body", "ticket_id"]}), 400

    msg = build_message(*message_args)
    send_message(msg)
    return jsonify({"Success": "Consultant has been emailed"}), 200


def build_message(consultant, subject, body, html_body, ticket_id):
    msg = EmailMessage()
    msg['From'] = BOT_ADDRESS
    msg['To'] = consultant
    msg['CC'] = CC_ADDRESS
    msg['Subject'] = subject
    msg.add_header('Ticket-ID', str(ticket_id))
    msg.set_content(html_body, subtype='html')
    return msg


def send_message(msg):
    service = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    service.starttls()
    service.login(BOT_ADDRESS, BOT_PASSWORD)
    service.send_message(msg)
    service.quit()


if __name__ == "__main__":
    app.run(debug=True)

