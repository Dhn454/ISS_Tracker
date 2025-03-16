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
    """
    Parses ISS trajectory XML data into a list of dictionaries.

    Args:
        xml_data (str): XML data as a string.

    Returns:
        list[dict]: List of state vectors with EPOCH, position, and velocity.
    """
    root = ET.fromstring(xml_data)
    state_vectors = []

    for state in root.findall(".//stateVector"):
        epoch = state.find("EPOCH")
        x = state.find("X")
        y = state.find("Y")
        z = state.find("Z")
        x_dot = state.find("X_DOT")
        y_dot = state.find("Y_DOT")
        z_dot = state.find("Z_DOT")

        if epoch is None or x is None or y is None or z is None or x_dot is None or y_dot is None or z_dot is None:
            logging.error(f"Missing fields in state vector: {ET.tostring(state, encoding='unicode')}")
            continue  # Skip this entry if any field is missing

        state_vectors.append({
            "EPOCH": epoch.text,
            "X": float(x.text),
            "Y": float(y.text),
            "Z": float(z.text),
            "X_DOT": float(x_dot.text),
            "Y_DOT": float(y_dot.text),
            "Z_DOT": float(z_dot.text)
        })

    logging.debug(f"Final parsed state vectors: {state_vectors}")
    return state_vectors

def convert_cartesian_to_geo(x: float, y: float, z: float) -> dict:
    """
    Converts Cartesian coordinates to latitude, longitude, and altitude.

    Args:
        x (float): X coordinate in km.
        y (float): Y coordinate in km.
        z (float): Z coordinate in km.

    Returns:
        dict: Dictionary with latitude, longitude, altitude, and geoposition.
    """
    try:
        # Sample conversion logic (Replace with actual conversion logic)
        latitude = math.degrees(math.atan2(z, math.sqrt(x**2 + y**2)))
        longitude = math.degrees(math.atan2(y, x))
        altitude = math.sqrt(x**2 + y**2 + z**2) - 6371  # Approximate Earth radius subtraction

        # Use Geopy to find location (this might be causing the error)
        geolocator = Nominatim(user_agent="iss_tracker")
        location = geolocator.reverse((latitude, longitude), exactly_one=True)

        geoposition = location.address if location else "Unknown Location"

        geo_data = {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "geoposition": geoposition
        }

        logging.debug(f"Geo conversion output: {geo_data}")

        return geo_data

    except Exception as e:
        logging.error(f"Error in convert_cartesian_to_geo: {str(e)}")
        return {
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "geoposition": "Error retrieving location"
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
    Fetch ISS trajectory data, parse it, and store it in Redis.
    """
    logging.info("Loading ISS data into Redis...")

    xml_data = fetch_iss_data()
    if not xml_data:
        logging.error("No XML data fetched. Cannot load into Redis.")
        return

    state_vectors = parse_iss_data(xml_data)
    
    if not state_vectors:
        logging.error("No valid state vectors parsed from XML data.")
        return

    for state in state_vectors:
        logging.debug(f"Processing state: {state}")  # Log each state

        if "EPOCH" not in state:
            logging.error(f"Missing 'EPOCH' key in state: {state}")
            continue  # Skip this entry if it lacks 'EPOCH'

        # Ensure all required fields are present
        required_fields = {"X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT"}
        if not required_fields.issubset(state.keys()):
            logging.error(f"Missing keys in parsed state: {set(required_fields) - set(state.keys())}")
            continue

        epoch = state["EPOCH"]
        data = {
            "x": str(state["X"]),  # Store as string to prevent Redis formatting issues
            "y": str(state["Y"]),
            "z": str(state["Z"]),
            "x_dot": str(state["X_DOT"]),
            "y_dot": str(state["Y_DOT"]),
            "z_dot": str(state["Z_DOT"])
        }

        logging.debug(f"Storing in Redis: epoch={epoch}, data={data}")

        redis_client.hset(f"epoch:{epoch}", mapping=data)

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


from datetime import datetime, timezone

def find_closest_epoch(state_vectors):
    """
    Finds the state vector with the EPOCH closest to the current time.

    Args:
        state_vectors (list[dict]): List of state vectors.

    Returns:
        dict: The state vector closest to the current time.
    """
    current_time = datetime.now(timezone.utc)

    def parse_epoch(epoch_str):
        """
        Parses an epoch string after removing Redis prefix 'epoch:' if present.
        """
        cleaned_epoch = epoch_str.replace("epoch:", "")  # Remove prefix
        parsed_time = datetime.strptime(cleaned_epoch, "%Y-%jT%H:%M:%S.%fZ")
        return parsed_time.replace(tzinfo=timezone.utc)  # Force timezone awareness

    closest_state = min(
        state_vectors,
        key=lambda state: abs(parse_epoch(state["epoch"]) - current_time)
    )

    return closest_state


@app.route('/epochs', methods=['GET'])
def get_epochs():
    """
    Returns a list of all available epochs stored in Redis.

    Query parameters:
    - limit (int, optional): Limit the number of returned epochs.
    - offset (int, optional): Number of epochs to skip before returning results.

    Returns:
        JSON: List of available epochs.
    """
    try:
        redis_keys = redis_client.keys("epoch:*")  # Get all epoch keys
        epochs = [key.replace("epoch:", "") for key in redis_keys]  # Remove "epoch:" prefix

        # Sorting to ensure chronological order
        epochs.sort()

        # Apply pagination
        limit = request.args.get("limit", type=int)
        offset = request.args.get("offset", type=int, default=0)

        if limit:
            epochs = epochs[offset:offset + limit]
        else:
            epochs = epochs[offset:]

        logging.debug(f"Returning epochs: {epochs}")
        return jsonify({"epochs": epochs})

    except Exception as e:
        logging.error(f"Error in /epochs route: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route('/epochs/<epoch>', methods=['GET'])
def get_epoch(epoch):
    """
    Returns the state vector for a given epoch.

    Args:
        epoch (str): The epoch timestamp.

    Returns:
        JSON: State vector details including position and velocity.
    """
    try:
        decoded_epoch = f"epoch:{epoch}"  # Redis stores keys with "epoch:" prefix
        data = redis_client.hgetall(decoded_epoch)

        if not data:
            logging.error(f"Epoch '{epoch}' not found in Redis")
            return jsonify({"error": f"Epoch '{epoch}' not found"}), 404

        # Convert stored string values to floats
        response = {
            "epoch": epoch,
            "position": {
                "x": float(data["x"]),
                "y": float(data["y"]),
                "z": float(data["z"])
            },
            "velocity": {
                "x_dot": float(data["x_dot"]),
                "y_dot": float(data["y_dot"]),
                "z_dot": float(data["z_dot"])
            }
        }

        return jsonify(response)

    except Exception as e:
        logging.error(f"Error in /epochs/<epoch> route: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route('/epochs/<epoch>/speed', methods=['GET'])
def get_epoch_speed(epoch):
    """
    Returns the speed of the ISS at a given epoch.

    Args:
        epoch (str): The epoch timestamp.

    Returns:
        JSON: The ISS speed at the requested epoch.
    """
    try:
        decoded_epoch = f"epoch:{epoch}"  # Redis stores keys with "epoch:" prefix

        # Fetch data from Redis
        data = redis_client.hgetall(decoded_epoch)
        logging.debug(f"Data retrieved for {epoch}: {data}")

        if not data:
            logging.error(f"Epoch '{epoch}' not found in Redis")
            return jsonify({"error": f"Epoch '{epoch}' not found"}), 404

        # Extract velocity components
        x_dot = float(data.get("x_dot", 0))
        y_dot = float(data.get("y_dot", 0))
        z_dot = float(data.get("z_dot", 0))

        # Compute speed
        speed = calculate_speed((x_dot, y_dot, z_dot))

        return jsonify({"epoch": epoch, "speed": speed})

    except Exception as e:
        logging.error(f"Error in /epochs/<epoch>/speed route: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


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

'''
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
            logging.info(f"Retrieved data from Redis: {data}")
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
'''
'''
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
        logging.debug("Fetching state vectors from Redis...")
        state_vectors = []
        redis_keys = redis_client.keys("epoch:*")
        logging.debug(f"Redis keys found: {redis_keys}")

        for key in redis_keys:
            data = redis_client.hgetall(key)
            logging.debug(f"Raw data from Redis: {data}")

            # No need to decode, as decode_responses=True already returns strings
            state_vectors.append({
                "epoch": key,  # Redis key is already a string
                "position": (float(data["x"]), float(data["y"]), float(data["z"])),
                "velocity": (float(data["x_dot"]), float(data["y_dot"]), float(data["z_dot"]))
            })

        if not state_vectors:
            logging.error("No ISS data available in Redis.")
            return jsonify({"error": "No ISS data available"}), 500

        # Find the closest epoch using state_vectors
        closest_vector = find_closest_epoch(state_vectors)
        logging.debug(f"Closest vector found: {closest_vector}")

        # Extract position
        x, y, z = closest_vector["position"]
        logging.debug(f"Converting position: {x}, {y}, {z}")

        # Convert Cartesian to geolocation (lat, long, alt)
        geo_data = convert_cartesian_to_geo(x, y, z)
        logging.debug(f"Geo Data: {geo_data}")

        # Compute instantaneous speed
        speed = calculate_speed(closest_vector["velocity"])
        logging.debug(f"Calculated Speed: {speed}")

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
'''

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
        logging.debug("Fetching state vectors from Redis...")
        state_vectors = []
        redis_keys = redis_client.keys("epoch:*")
        logging.debug(f"Redis keys found: {redis_keys}")

        for key in redis_keys:
            data = redis_client.hgetall(key)
            logging.debug(f"Raw data from Redis (key={key}): {data}")

            # Ensure required fields exist
            required_fields = {"x", "y", "z", "x_dot", "y_dot", "z_dot"}
            if not required_fields.issubset(data.keys()):
                logging.error(f"Missing keys in Redis data: {set(required_fields) - set(data.keys())}")
                continue

            # Convert numeric values from strings to floats
            state_vectors.append({
                "epoch": key.replace("epoch:", ""),
                "position": (float(data["x"]), float(data["y"]), float(data["z"])),
                "velocity": (float(data["x_dot"]), float(data["y_dot"]), float(data["z_dot"]))
            })

        if not state_vectors:
            logging.error("No valid ISS data available in Redis.")
            return jsonify({"error": "No ISS data available"}), 500

        # Find the closest epoch using state_vectors
        closest_vector = find_closest_epoch(state_vectors)
        logging.debug(f"Closest vector found: {closest_vector}")

        # Extract position
        x, y, z = closest_vector["position"]
        logging.debug(f"Converting position: {x}, {y}, {z}")

        # Convert Cartesian to geolocation (lat, long, alt)
        geo_data = convert_cartesian_to_geo(x, y, z)
        logging.debug(f"Geo Data: {geo_data}")

        # Compute instantaneous speed
        speed = calculate_speed(closest_vector["velocity"])
        logging.debug(f"Calculated Speed: {speed}")

        return jsonify({
            "epoch": closest_vector["epoch"],
            "latitude": geo_data.get("latitude", None),
            "longitude": geo_data.get("longitude", None),
            "altitude": geo_data.get("altitude", None),
            "geoposition": geo_data.get("geoposition", "Unknown Location"),
            "speed": speed
        })

    except Exception as e:
        logging.error(f"Error in /now route: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


if __name__ == "__main__":
    load_data_to_redis()  # Ensure data is loaded when app starts
    print(redis_client.keys("epoch:*"))

    app.run(host='0.0.0.0', port=5000)
