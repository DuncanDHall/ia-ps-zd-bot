from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest

import smtplib
from email.message import EmailMessage

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


# payload structure:
# {
#     "ticket_id": Int,
#     "consultant": "<consultant>@archive.org",
#     "subject": String,
#     "body": String,
#     "html_body": String,
# }

@app.route("/consult.json", methods=['POST'])
def consult():
    try:
        json = request.get_json()
        print("JSON? >> ", json)
    except BadRequest as e:
        return jsonify({"Error": "Bad Request: Could not parse json object"}), 400

    msg = build_message(json['consultant'], json['subject'], json['body'], json['ticket_id'])
    send_message(msg)
    return jsonify({"Success": "Consultant has been emailed"}), 200


def build_message(consultant, subject, body, ticket_id):
    msg = EmailMessage()
    msg['From'] = 'dhall.testmail@gmail.com'
    msg['To'] = consultant
    msg['CC'] = 'aezyer.spam@gmail.com'
    msg['Subject'] = subject
    msg.add_header('Ticket-ID', str(ticket_id))
    msg.set_content(body)
    # msg.set_content(html_body, subtype='html')
    return msg


def send_message(msg):
    smtp_host = 'smtp.gmail.com'
    smtp_port = 587
    smtp_mode = "tls"
    smtp_login = 'dhall.testmail@gmail.com'
    smtp_password = "vvdrtcinqsfhysiv"

    service = smtplib.SMTP(smtp_host, smtp_port)
    service.starttls()
    service.login(smtp_login, smtp_password)
    service.send_message(msg)
    service.quit()



if __name__ == "__main__":
    app.run(debug=True)

