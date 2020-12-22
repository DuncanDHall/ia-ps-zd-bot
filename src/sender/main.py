from os import environ as env

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

from shared.config import *
from shared.custom_logging import logger
from shared import mail

app = Flask("zd-mailbot")

# Test with:
# curl http://0.0.0.0:5000/consult.json -X POST -u zendesk -H "Content-Type: application/json" --data '{"consultant": "dhall.sub@icloud.com", "subject": "Make sure this works", "body": "This is a test", "html_body": "This is a test <b>(html)</b>", "ticket_id": 257064}'

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
        return request.get_json(), 200


@app.route("/consult.json", methods=['POST'])
def consult():
    """
    payload structure:
        {
            "ticket_id": Int,
            "consultant": "<consultant>@archive.org, ...",
            "subject": String,
            "body": String,
            "html_body": String,
        }
    :return:
    """
    logger.info("{} request from {}".format(request.method, request.origin))
    auth = request.authorization
    if auth is None:
        message = "Provide basic auth to use this service."
        logger.error(message)
        return jsonify({"Error": message}), 401
    if (auth['username'] != env['ZENDESK_TRIGGER_USERNAME'] or
            auth['password'] != env['ZENDESK_TRIGGER_PASSWORD']):
        message = "Invalid Username/Password"
        logger.error(message)
        return jsonify({"Error": message}), 401

    try:
        json = request.get_json()
    except BadRequest as e:
        message = "Bad Request: Could not parse json object"
        logger.error(message)
        return jsonify({"Error": message}), 400

    # verify correct keys
    required_keys = ['consultant', 'subject', 'body', 'html_body', 'ticket_id']
    if any(map(lambda k: k not in json, required_keys)):
        logger.error("Invalid data keys")
        return jsonify({"Error": "Json object must contain the following non-optional keys",
                        "keys": ["consultant", "subject", "body", "html_body", "ticket_id"]}), 400

    # send mail
    body = INTERNAL_MESSAGE_PLAIN + json['body']
    html_body = INTERNAL_MESSAGE_HTML + json['html_body']
    body = body.replace('\\n', '\n')
    html_body = html_body.replace('\\n', '\n')
    for consultant in json['consultant'].replace(' ', '').split(','):
        mail.send_mail(
            sender='{} <{}>'.format(MAILBOT_NAME, env['MAILBOT_ADDRESS']),
            receiver=consultant,
            subject=SUBJECT_PATTERN.format(json['ticket_id'], json['subject']),
            body=body,
            html_body = html_body,
            cc=['{} <{}>'.format(MAILBOT_CC_NAME, env['MAILBOT_CC_ADDRESS'])]
        )
    return jsonify({"Success": "Consultant has been emailed"}), 200


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

