"""
iss_tracker.py
--------------
This Flask API fetches and processes ISS trajectory data from NASA's public dataset and stores it in a Redis database.
It provides multiple routes to query ISS position, velocity, and speed.

Routes:
- `/epochs`: Returns all ISS state vectors.
- `/epochs?limit=int&offset=int`: Returns paginated state vectors.
- `/epochs/<epoch>`: Returns state vector for a specific epoch.
- `/epochs/<epoch>/speed`: Returns the ISS speed at a specific epoch.
- `/epochs/<epoch>/location`: Returns the ISS latitude, longitude, altitude, and geoposition.
- `/now`: Returns the ISS state vector closest to the current time.

Author: Dominic Nguyen
Date: 02/25/2025

Sources:
- NASA ISS OEM Data: https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml
- Flask Documentation: https://flask.palletsprojects.com/
- XML Parsing in Python: https://docs.python.org/3/library/xml.etree.elementtree.html
- Redis Python Client: https://redis-py.readthedocs.io/en/stable/
"""

import requests
import xml.etree.ElementTree as ET
import math
import logging
import redis
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from geopy.geocoders import Nominatim

# Initialize Flask app
app = Flask(__name__)

# Configure Redis connection
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

# NASA ISS Trajectory Data URL
ISS_XML_URL = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"

def fetch_iss_data():
    """Fetches ISS trajectory data from NASA's API."""
    logging.info("Fetching ISS trajectory data...")
    response = requests.get(ISS_XML_URL)
    if response.status_code != 200:
        logging.error("Failed to retrieve ISS trajectory data.")
        return None
    return response.text

def parse_iss_data(xml_data):
    """Parses ISS XML data and extracts state vectors."""
    root = ET.fromstring(xml_data)
    state_vectors = []

    for segment in root.findall(".//segment"):
        for data in segment.findall(".//data"):
            for state_vector in data.findall(".//stateVector"):
                epoch = state_vector.find("EPOCH").text
                x = float(state_vector.find("X").text)
                y = float(state_vector.find("Y").text)
                z = float(state_vector.find("Z").text)
                x_dot = float(state_vector.find("X_DOT").text)
                y_dot = float(state_vector.find("Y_DOT").text)
                z_dot = float(state_vector.find("Z_DOT").text)

                state_vectors.append({
                    "epoch": epoch,
                    "position": (x, y, z),
                    "velocity": (x_dot, y_dot, z_dot)
                })

    return state_vectors

def load_data_to_redis():
    """Loads ISS trajectory data into Redis if it isn't already stored."""
    if redis_client.exists("epochs"):
        return  # Data already exists in Redis, skip loading

    xml_data = fetch_iss_data()
    if not xml_data:
        logging.error("No data to load into Redis.")
        return

    state_vectors = parse_iss_data(xml_data)
    for sv in state_vectors:
        redis_client.hset(f"epoch:{sv['epoch']}", mapping={
            "position": str(sv["position"]),
            "velocity": str(sv["velocity"])
        })
    redis_client.set("epochs", ",".join([sv["epoch"] for sv in state_vectors]))

def calculate_speed(velocity):
    """Calculates ISS speed using velocity components."""
    return math.sqrt(velocity[0]**2 + velocity[1]**2 + velocity[2]**2)

def convert_epoch_to_datetime(epoch):
    """Converts an ISS epoch timestamp into a Python datetime object."""
    return datetime.strptime(epoch, "%Y-%jT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

def find_closest_epoch():
    """Finds the ISS state vector closest to the current time."""
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    epochs = redis_client.get("epochs").split(",")

    closest_epoch = min(epochs, key=lambda e: abs(convert_epoch_to_datetime(e) - now))
    return closest_epoch

@app.route('/epochs', methods=['GET'])
def get_epochs():
    """Returns all epochs, with optional pagination."""
    epochs = redis_client.get("epochs").split(",") if redis_client.exists("epochs") else []
    limit = int(request.args.get('limit', len(epochs)))
    offset = int(request.args.get('offset', 0))

    return jsonify({"epochs": epochs[offset:offset + limit]})

@app.route('/epochs/<epoch>', methods=['GET'])
def get_epoch(epoch):
    """Returns the ISS state vector for a specific epoch."""
    decoded_epoch = epoch.replace("%20", " ")  # Handle spaces in URLs
    if redis_client.exists(f"epoch:{decoded_epoch}"):
        return jsonify(redis_client.hgetall(f"epoch:{decoded_epoch}"))
    return jsonify({"error": f"Epoch '{decoded_epoch}' not found"}), 404

@app.route('/epochs/<epoch>/speed', methods=['GET'])
def get_epoch_speed(epoch):
    """Returns the ISS speed at a specific epoch."""
    decoded_epoch = epoch.replace("%20", " ")
    if redis_client.exists(f"epoch:{decoded_epoch}"):
        velocity = eval(redis_client.hget(f"epoch:{decoded_epoch}", "velocity"))
        return jsonify({"epoch": decoded_epoch, "speed": calculate_speed(velocity)})
    return jsonify({"error": f"Epoch '{decoded_epoch}' not found"}), 404

@app.route('/epochs/<epoch>/location', methods=['GET'])
def get_epoch_location(epoch):
    """Returns the ISS latitude, longitude, altitude, and geoposition for a given epoch."""
    decoded_epoch = epoch.replace("%20", " ")
    if redis_client.exists(f"epoch:{decoded_epoch}"):
        position = eval(redis_client.hget(f"epoch:{decoded_epoch}", "position"))
        lat, lon, alt = position[0], position[1], position[2]

        geolocator = Nominatim(user_agent="geoapiExercises")
        location = geolocator.reverse((lat, lon), language="en")

        return jsonify({
            "epoch": decoded_epoch,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "geoposition": location.address if location else "Unknown"
        })
    return jsonify({"error": f"Epoch '{decoded_epoch}' not found"}), 404

@app.route('/now', methods=['GET'])
def get_now():
    """Returns the ISS state vector closest to the current time."""
    closest_epoch = find_closest_epoch()
    return get_epoch_location(closest_epoch)

if __name__ == "__main__":
    load_data_to_redis()  # Ensure data is loaded when app starts
    app.run(host='0.0.0.0', port=5000)

