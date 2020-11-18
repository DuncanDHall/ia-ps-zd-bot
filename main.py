import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest
import smtplib
from email.message import EmailMessage

from config import *

app = Flask("zd-mailbot")

# Test with:
# curl http://0.0.0.0:5000/consult.json -X POST -H "Content-Type: application/json" --data '{"consultant": "dhall.sub@icloud.com", "subject": "Make sure this works", "body": "This is a test", "html_body": "This is a test <b>(html)</b>", "ticket_id": 257064}'

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


def build_message(rcpt, subject, body, html_body=None, ticket_id=None, include_internal_message=True):

    def format_with_ticket_id(subject, ticket_id):
        return SUBJECT_PATTERN.format(ticket_id, subject)

    msg = EmailMessage()
    msg['From'] = os.environ['MAILBOT_ADDRESS']
    msg['To'] = rcpt
    msg['CC'] = os.environ['MAILBOT_CC_ADDRESS']
    if ticket_id:
        msg['Subject'] = format_with_ticket_id(subject, ticket_id)
        msg.add_header('Ticket-ID', str(ticket_id))
    else:
        msg['Subject'] = subject
    if include_internal_message:
        msg.set_content(INTERNAL_MESSAGE + body)
    else:
        msg.set_content(body)
    if html_body is not None:
        msg.add_alternative(html_body, subtype='html')
    return msg


def send_message(msg):
    service = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    service.starttls()
    # print(os.environ['MAILBOT_ADDRESS'], os.environ['MAILBOT_GMAIL_PASSWORD'])
    service.login(os.environ['MAILBOT_ADDRESS'], os.environ['MAILBOT_GMAIL_PASSWORD'])
    service.send_message(msg)
    service.quit()


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

