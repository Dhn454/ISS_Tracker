"""
iss_tracker.py
--------------
This Flask API fetches and processes ISS trajectory data from NASA's public dataset and stores it in a Redis database.
It provides multiple routes to query ISS position, velocity, and speed.

Routes:
- /epochs: Returns all ISS state vectors.
- /epochs?limit=int&offset=int: Returns paginated state vectors.
- /epochs/<epoch>: Returns state vector for a specific epoch.
- /epochs/<epoch>/speed: Returns the ISS speed at a specific epoch.
- /epochs/<epoch>/location: Returns the ISS latitude, longitude, altitude, and geoposition.
- /now: Returns the ISS state vector closest to the current time.

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
import json

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

def convert_cartesian_to_geo(x: float, y: float, z: float):
    """
    Converts Cartesian coordinates (x, y, z) into geographic coordinates: 
    latitude, longitude, and altitude.

    Parameters:
        x (float): X position in km
        y (float): Y position in km
        z (float): Z position in km

    Returns:
        dict: A dictionary with latitude, longitude, and altitude
    """
    from math import sqrt, atan2, degrees
    import geopy

    # Constants
    R_EARTH = 6371  # Approximate radius of Earth in km

    # Compute longitude and latitude
    longitude = degrees(atan2(y, x))
    latitude = degrees(atan2(z, sqrt(x**2 + y**2)))

    # Compute altitude
    altitude = sqrt(x**2 + y**2 + z**2) - R_EARTH

    return {
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude
    }

def load_iss_data():
    """
    Loads ISS data from NASA's API, parses it, and stores it in `state_vectors`.

    Modifies:
    - `state_vectors` (global variable) to store parsed ISS trajectory data.
    """
    global state_vectors  # Ensure global variable is modified
    xml_data = fetch_iss_data()  # Fetch XML data

    if xml_data:
        state_vectors = parse_iss_data(xml_data)  # Parse and store data
    else:
        logging.warning("No ISS data fetched. `state_vectors` remains empty.")
        state_vectors = []

def load_data_to_redis():
    """
    Loads ISS trajectory data into Redis.

    Fetches data from NASA's API (if not already in Redis), parses it, and stores it in Redis.
    Ensures that data persists across app restarts.

    Modifies:
    - Stores ISS trajectory data in Redis under the key "iss_state_vectors".
    """
    if redis_client.exists("iss_state_vectors"):
        logging.info("Data already exists in Redis. Skipping reload.")
        return  # Data is already loaded

    xml_data = fetch_iss_data()
    if not xml_data:
        logging.error("Failed to fetch ISS data. No data will be loaded into Redis.")
        return

    state_vectors = parse_iss_data(xml_data)
    redis_client.set("iss_state_vectors", json.dumps(state_vectors))  # Store in Redis
    logging.info("ISS data successfully loaded into Redis.")
    
def calculate_speed(velocity):
    """Calculates ISS speed using velocity components."""
    return math.sqrt(velocity[0]**2 + velocity[1]**2 + velocity[2]**2)

def compute_average_speed(state_vectors):  # This should match test_iss_tracker.py
    """Calculates the average speed based on ISS velocity data."""
    speeds = [calculate_speed(sv["velocity"]) for sv in state_vectors]
    return sum(speeds) / len(speeds) if speeds else 0

def convert_epoch_to_datetime(epoch):
    """Converts an ISS epoch timestamp into a Python datetime object."""
    return datetime.strptime(epoch, "%Y-%jT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

def find_closest_epoch(state_vectors):
    """
    Finds the ISS state vector closest to the current time.

    Parameters:
    - state_vectors (list): A list of dictionaries containing ISS state vector data.

    Returns:
    - dict: The closest state vector to the current time.

    Raises:
    - ValueError: If the list is empty.
    """
    if not state_vectors:
        raise ValueError("State vector list is empty. Cannot find the closest epoch.")

    now = datetime.now(timezone.utc)  # Get current time in UTC

    try:
        # Debug: Print available epochs
        print(f"DEBUG: Available epochs: {[sv['epoch'] for sv in state_vectors]}")

        closest = min(
            state_vectors, key=lambda sv: abs(convert_epoch_to_datetime(sv["epoch"]) - now)
        )

        # Debug: Show closest epoch found
        print(f"DEBUG: Closest epoch found: {closest['epoch']}")

        return closest

    except Exception as e:
        print(f"ERROR: Issue in find_closest_epoch(): {str(e)}")
        raise


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

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

@app.route('/epochs/<epoch>/location', methods=['GET'])
def get_epoch_location(epoch):
    """Returns latitude, longitude, altitude, and geoposition for a given epoch."""
    try:
        decoded_epoch = epoch.replace("%20", " ")  # Handle URL encoding
        if not redis_client.exists(decoded_epoch):
            return jsonify({"error": f"Epoch '{decoded_epoch}' not found in Redis"}), 404

        # Retrieve data from Redis
        data = redis_client.hgetall(decoded_epoch)
        x, y, z = float(data[b'x']), float(data[b'y']), float(data[b'z'])

        # Convert Cartesian to latitude, longitude, altitude
        latitude, longitude, altitude = convert_cartesian_to_geo(x, y, z)

        # Get geoposition using GeoPy
        geolocator = Nominatim(user_agent="iss_tracker")
        try:
            location = geolocator.reverse((latitude, longitude), language="en", timeout=10)
            geoposition = location.address if location else "Unknown Location"
        except Exception as e:
            logging.error(f"GeoPy error: {e}")
            geoposition = "GeoPy Failed"

        return jsonify({
            "epoch": decoded_epoch,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "geoposition": geoposition
        })

    except Exception as e:
        logging.error(f"Error in /epochs/<epoch>/location: {e}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route('/now', methods=['GET'])
def get_now_location():
    """
    Returns the ISS state vector closest to the current time, including:
    - Epoch timestamp
    - Latitude, Longitude, Altitude
    - Geoposition (city, country)
    - Instantaneous speed
    """
    try:
        # Retrieve state vectors from Redis
        state_vectors = []
        for key in redis_client.keys("epoch:*"):
            data = redis_client.hgetall(key)

            # Decode the key and values properly
            key = key.decode("utf-8") if isinstance(key, bytes) else key
            data = {k.decode("utf-8"): v.decode("utf-8") for k, v in data.items()}

            # Convert numeric values from strings to floats
            state_vectors.append({
                "epoch": key,
                "position": (float(data["x"]), float(data["y"]), float(data["z"])),
                "velocity": (float(data["x_dot"]), float(data["y_dot"]), float(data["z_dot"]))
            })

        if not state_vectors:
            return jsonify({"error": "No ISS data available"}), 500

        # Find the closest epoch using state_vectors
        closest_vector = find_closest_epoch(state_vectors)

        # Extract position
        x, y, z = closest_vector["position"]

        # Convert Cartesian to geolocation (lat, long, alt)
        geo_data = convert_cartesian_to_geo(x, y, z)

        # Compute instantaneous speed
        speed = calculate_speed(closest_vector["velocity"])

        return jsonify({
            "epoch": closest_vector["epoch"],
            "latitude": geo_data["latitude"],
            "longitude": geo_data["longitude"],
            "altitude": geo_data["altitude"],
            "geoposition": geo_data["geoposition"],
            "speed": speed
        })

    except Exception as e:
        logging.error(f"Error in /now route: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


if __name__ == "__main__":
    load_data_to_redis()  # Ensure data is loaded when app starts
    app.run(host='0.0.0.0', port=5000)
