# Use Python 3.8 as the base image
FROM python:3.8

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app/

# Install dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Expose Flask app on port 5000
EXPOSE 5000

# Run the Flask app
CMD ["python3", "iss_tracker.py"]

