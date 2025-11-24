# Use the official Python image as the base image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that the Flask app is running on
EXPOSE 8000

# Set the command to run the Flask app
CMD ["gunicorn", "-w", "1", "-t", "0", "-b", "0.0.0.0:8000", "main:app"]