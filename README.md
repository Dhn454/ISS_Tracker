# **ISS Trajectory Tracker – Flask API**

## **Overview**
This project is a **Flask-based web application** that provides real-time access to **International Space Station (ISS) trajectory data**. The API allows users to retrieve **state vectors** (position and velocity data) for various timestamps (epochs) and calculate the ISS's instantaneous speed. This project extends previous work by integrating the logic into a **containerized Flask web service** that can be easily deployed and queried.

Tracking ISS data is crucial for **space situational awareness**, **orbital mechanics research**, and **satellite communication planning**. This project provides an **accessible way to interact with the ISS’s trajectory** using REST API endpoints.

---

## **📥 Accessing the ISS Data Set**

The ISS state vectors data is obtained from **NASA’s ISS Trajectory Data website**:  
[🔗 ISS Trajectory Data (OEM)](https://spotthestation.nasa.gov)

There are two data formats available:  
- **TXT format:** `https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.txt`  
- **XML format:** `https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml`

**NOTE:** The dataset contains ISS state vectors over a **15-day period**, where each state vector includes:  
- **Epoch (timestamp)**
- **Position:** `{X, Y, Z}` (in km)
- **Velocity:** `{X_DOT, Y_DOT, Z_DOT}` (in km/s)  

This API ingests the **XML format** for easier data parsing.

---

## **🐳 Deploying with Docker Compose**
### **1️⃣ Clone the Repository and Navigate to the Project Directory**
```bash
git clone https://github.com/Dhn454/ISS_Tracker.git
cd ISS_Tracker
```
### **2️⃣ Build and Start the Containers**
```bash
docker-compose up --build -d
```
This command will:
- Build the Flask API container.
- Start the Redis container for data storage.
- Expose the API on **`http://localhost:5000`**.

### **3️⃣ Verify Running Containers**
```bash
docker ps
```
Expected output:
```
CONTAINER ID   IMAGE             STATUS          PORTS
flask-iss      flask-iss-tracker Up 10 minutes  0.0.0.0:5000->5000/tcp
redis         redis:latest      Up 10 minutes  6379/tcp
```

### **4️⃣ Stop the Containers**
```bash
docker-compose down
```

---

## **🔗 API Endpoints & Testing with `curl`**

### **1️⃣ Retrieve All Available Epochs**
```bash
curl -X GET "http://localhost:5000/epochs"
```

### **2️⃣ Retrieve Paginated Epochs**
```bash
curl -X GET "http://localhost:5000/epochs?limit=5&offset=2"
```

### **3️⃣ Retrieve State Vector for a Specific Epoch**
```bash
curl -X GET "http://localhost:5000/epochs/2025-088T12:00:00.000Z"
```

### **4️⃣ Retrieve Speed at a Specific Epoch**
```bash
curl -X GET "http://localhost:5000/epochs/2025-088T12:00:00.000Z/speed"
```

### **5️⃣ Retrieve ISS Location at a Specific Epoch**
```bash
curl -X GET "http://localhost:5000/epochs/2025-088T12:00:00.000Z/location"
```

### **6️⃣ Retrieve Real-Time ISS Data (Closest Epoch)**
```bash
curl -X GET "http://localhost:5000/now"
```

---
## **🧪 Running Unit Tests in the Container**
1️⃣ **Run tests inside the Flask container:**
```bash
docker-compose exec flask-iss pytest test_iss_tracker.py
```

2️⃣ **Expected Output:**
```plaintext
============================= test session starts =============================
collected 6 items

test_iss_tracker.py ... ✅ ✅ ✅ ✅ ✅ ✅
============================== 6 passed in 2.50s ==============================
```

---
## **📊 System Diagram**
This diagram illustrates how the **Flask API interacts with users and ISS data**.

```plaintext
                        +--------------------------------------+
                        |        User (Client)                |
                        |  - Sends HTTP Requests via cURL     |
                        |  - Receives JSON Responses          |
                        +------------------+-----------------+
                                           |
                                           v
                        +------------------+-----------------+
                        |      Flask API (Containerized)      |
                        |--------------------------------------|
                        |  - Serves API endpoints via Flask   |
                        |  - Fetches ISS trajectory data      |
                        |  - Calculates ISS speed            |
                        |  - Parses XML data format          |
                        +------------------+-----------------+
                                           |
       -----------------------------------------------------------------------
       |                                 |                                     |
       v                                 v                                     v
+--------------------+       +---------------------------+       +---------------------------+
|  /epochs          |       |  /epochs/<epoch>          |       |  /epochs/<epoch>/speed    |
|--------------------|       |---------------------------|       |---------------------------|
|  - Returns all    |       |  - Returns state vectors  |       |  - Returns speed at       |
|    ISS epochs     |       |    for a specific epoch   |       |    a specific epoch       |
+--------------------+       +---------------------------+       +---------------------------+

                         |
                         v
       +----------------------------------+
       |  ISS Data Source (NASA API)     |
       |----------------------------------|
       |  - XML Ephemeris Data           |
       |  - 15-Day Trajectory Data       |
       |  - Contains {Epoch, Pos, Vel}   |
       +----------------------------------+
```

🚀 **Now you can deploy, test, and run the ISS Tracker API with ease!** 🚀


