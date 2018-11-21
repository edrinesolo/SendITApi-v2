from flask import jsonify, request, Blueprint
import psycopg2
from app.database.database import Database
from flask import current_app as app
from flask_mail import Message,Mail
import os
from app.auth.decorator import response_message, token_required
import re

from app.util.helper import Helper

ap = Blueprint('parcels', __name__)
db = Database()


@ap.route("/")
@token_required
def welcome(current_user):
    return response_message("ok", "Welcome to the sendit api v2", 200)


# GET parcels

@ap.route('/api/v2/parcels')
@token_required
def get_parcels(current_user):
    if not db.is_admin(current_user.user_id):
        return response_message('Forbidden operation', 'Only admin users can view all orders', 403)

    '''
        returns a list of all order requests
    '''
    all = db.get_all_parcels()
    if all:
        parcel_list = []
        for parcel in all:
            parcel_dict = {
                "parcel_id": parcel[0],
                "user_id": parcel[1],
                "pickup_address": parcel[3],
                "destination_address": parcel[2],
                "sender_email": parcel[5],
                "recipient_email": parcel[10],
                "recipient_phone_number_number": parcel[7]
            }
            parcel_list.append(parcel_dict)
        return jsonify({"parcels": parcel_list}), 200
    return jsonify({'message': 'No parcel delivery orders posted yet', 'count': len(all)}), 404


# GET parcels/id
@ap.route('/api/v2/parcels/<int:id>')
@token_required
def get_a_parcel(current_user, id):
    """
    return order request details for a specific order
    :param id:
    :return:
    """
    if not db.is_admin(current_user.user_id):
        if str(current_user.user_id) != str(id):
            return response_message('Forbidden operation', 'You do not have permissions to access that', 403)
    if db.get_parcel_by_value('parcels', 'parcel_id', id) is None:
        return jsonify({"message": "parcel delivery request order not found"}), 404
    results = db.get_parcel_by_value('parcels', 'parcel_id', id)
    parcel_dict = {
        "parcel_id": results[0],
        "user_id": results[1],
        "pickup_address": results[3],
        "destination_address": results[2],
        "sender_email": results[5],
        "recipient_email": results[11],
        "recipient_phone_number": results[7],
        "current_location": results[10],
        "recipient fullname": results[12],
        "destination latlng ": results[14],
        "pickuplatlng": results[13],
        "weight":results[9],
        "distance(km)": results[16],
        "status":results[6],
        "price": results[15],
        "created": results[18],
        "last_modified": results[17],
        "parcel_description":results[4],
        "quantity":results[8]

    }
    return jsonify(parcel_dict), 200


# POST parcels
@ap.route('/api/v2/parcels', methods=['POST'])
@token_required
def add_parcel(current_user):
    """
    creates a new parcel order
    :return:
    """
    if not request.content_type == 'application/json':
        return jsonify({"failed": 'Content-type must be application/json'}), 415
    request_data = request.get_json()
    helper = Helper()
    try:
        if not is_valid(request_data['recipient_email']):
            return jsonify({"message": "Recipient email is invalid"}), 400
        if len(str(request_data['recipient_phone_number'])) < 10:
            return jsonify({"message": "Recipient Phone number should be atleast 10 characters"}), 400

        if len(str(request_data['parcel_description'])) < 5:
            return jsonify({"message": "Your Parcel description should be atleast 5 characters"}), 400
        if not isinstance(request_data['parcel_description'], str):
            return jsonify({"message": "Description should be string values"}), 400
        if not isinstance(request_data['pickup_address'], str):
            return jsonify({"message": "pickup_address should be string values"}), 400

        if not isinstance(request_data['destination_address'], str):
            return jsonify({"message": "destination_address should be string values"}), 400
        if not isinstance(request_data['quantity'], int):
            return jsonify({"message": "quantity should be integer values"}), 400

        if not isinstance(request_data['weight'], int):
            return jsonify({"message": "weight should be integer values"}), 400

        if not isinstance(request_data['recipient_name'],str):
            return jsonify({"message": "destination_address should be string values"}), 400


    except KeyError as keyerr:
        return response_message('Failed', str(keyerr) + 'is missing', 400)
    dest_lat_lng = helper.get_latlong(request_data['destination_address'])
    pickup_latlng = helper.get_latlong(request_data['pickup_address'])
    distance = helper.get_distance(pickup_latlng, dest_lat_lng)
    price = helper.get_charge(request_data['weight'], distance)

    if db.new_parcel_has_fishy_behaviour(current_user.user_id,request_data['recipient_email'],
                                         request_data['parcel_description']):
        return jsonify({"message":"Not allowed,similar order already placed"}),403

    try:

        db.insert_into_parcels(request_data['destination_address'],
                               request_data['pickup_address'],
                               request_data['parcel_description'],
                               current_user.user_id,
                               db.get_user_email(current_user.user_id),
                               request_data['recipient_name'],
                               request_data['recipient_email'],
                               request_data['recipient_phone_number'],
                               request_data['weight'],
                               request_data['quantity'],
                               pickup_latlng,
                               dest_lat_lng,
                               distance,
                               price)
    except psycopg2.IntegrityError:
        return response_message('Failed', 'Integrity Error:the user is being provided is inexistent', 403)
    return response_message('success', 'Parcel request has been created successfully', 201)


# PUT /parcels/<parcelId>/cancel
@ap.route('/api/v2/parcels/<int:id>/cancel', methods=['PUT'])
@token_required
def cancel_parcel_request(current_user,id):
    '''
    cancels a specific request given its identifier
    '''
    if db.get_parcel_by_value('parcels', 'parcel_id', id) is None:
        return jsonify({"message": "parcel delivery request not found"}), 404

    if db.is_order_delivered(id):
        return jsonify({"message": "Not allowed parcel request has already been delivered"}), 403
    if not db.is_parcel_owner(id, current_user.user_id):
        return jsonify({"message": "Not athorized"}), 403

    db.cancel_parcel(id)
    return jsonify(
        {"message": "parcel request was cancelled successfully"}), 200


@ap.route('/api/v2/parcels/<int:id>/presentLocation', methods=['PUT'])
@token_required
def change_present_location(current_user, id):
    if not db.is_admin(current_user.user_id):
        return response_message('Unauthorized', 'Not enough access privileges', 403)
    request_data = request.get_json()
    try:
        if not isinstance(request_data['current_location'], str):
            return response_message('error', 'current location should be string value', 400)
        if not db.get_parcel_by_value('parcels', 'parcel_id', id):
            return jsonify({'message': 'order not found'}), 404
        if is_should_update(request_data):
            db.change_present_location(request_data['current_location'], id)
            our_user = db.get_user_by_value('users', 'user_id', db.get_parce_owner_id(id))
            sendemail(our_user[3], 'Order Update',
                      'Hello there ' + our_user[1] + '\nYour parcels location is now ' + db.get_current_location(id))
            return jsonify({'message': 'current location updated successfully'}), 200
        else:
            return jsonify({'message': 'bad request object, current location missing'}), 400

    except KeyError as identifier:
        return jsonify({'message': str(identifier) + 'is missing'})


@ap.route('/api/v2/parcels/<int:id>/status', methods=['PUT'])
@token_required
def change_order_status(current_user, id):
    if not db.is_admin(current_user.user_id):
        return response_message('Unauthorized', 'Not enough access privileges', 403)
    request_data = request.get_json()
    try:

        if not isinstance(request_data['status'], str):
            return response_message('error', 'status should be string value', 400)
        status = ['pickup_started', 'rejected', 'in_transit', 'cancelled', 'delivered']

        if not db.get_parcel_by_value('parcels', 'parcel_id', id):
            return jsonify({'message': 'order not found'}), 404
        if not request_data['status'] in status:
            return jsonify(
                {'message': "invalid status,parcels can be cancelled,delivered,in_transit,rejected,pickup_started"}), 400

        db.change_status(request_data['status'], id)
        # TODO SEND AN EMAIL
        return jsonify({'message': 'order status updated successfully'}), 200
    except KeyError as e:
        return response_message('error','status is missing',400)





@ap.route('/api/v2/parcels/<int:id>/destination', methods=['PUT'])
@token_required
def change_destination(current_user, id):
    '''
    changes destination address
    '''
    rdata = request.get_json()
    if not "destination_address" in rdata:
        return jsonify({'message': 'Please add a new destination address'}), 400
    newdest = rdata['destination_address']
    if db.get_parcel_by_value('parcels', 'parcel_id', id) is None:
        return jsonify({"message": "parcel delivery request not found"}), 404
    if not db.is_order_delivered(id):
        if db.is_parcel_owner(id, current_user.user_id):
            db.change_destination(newdest, id)
            return jsonify({'message': 'destination updated successfully'}), 200
        else:
            response_message('Forbidden', 'Not authorised to perform operation', 403)

    else:
        return jsonify({'message': 'order already delivered cant update'}), 403


def not_validresponse():
    '''
    helper to refactor similar response
    '''
    return jsonify({"error": 'Bad Request object,expected data is missing'}), 400


def is_should_update(data):
    if 'current_location' in data:
        return True
    return False


def sendemail(email, subject, body):
    '''
    send an email to a user
    '''
    app.config.update(
        DEBUG=True,
        # EMAIL SETTINGS
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=465,
        MAIL_USE_SSL=True,
        MAIL_USERNAME=os.environ.get('trulysEmail'),
        MAIL_PASSWORD=os.environ.get('trulysPass')
    )
    mail = Mail(app)
    try:
        message = Message(subject,
                      sender="updates@sendit.com",
                      recipients=[email])
        message.body = body
        mail.send(message)
    except Exception as identifier:
        pass

def is_valid(email):
    """helper for checking valid emails"""

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False
    return True
