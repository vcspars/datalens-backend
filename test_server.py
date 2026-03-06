"""Simple test script to verify the server is working"""
import requests
import json

# Test the health endpoint
try:
    response = requests.get("http://localhost:8000/health")
    print(f"Health check: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"Health check failed: {e}")

# Test CORS configuration
try:
    response = requests.get("http://localhost:8000/debug/cors")
    print(f"CORS debug: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"CORS debug failed: {e}")

# Test signup endpoint
try:
    test_data = {
        "email": "test@example.com",
        "password": "test123",
        "full_name": "Test User",
        "confirm_password": "test123"
    }
    response = requests.post(
        "http://localhost:8000/api/auth/signup",
        json=test_data,
        headers={"Content-Type": "application/json"}
    )
    print(f"Signup test: {response.status_code}")
    if response.status_code != 201:
        print(f"Error: {response.text}")
    else:
        print(f"Success: {response.json()}")
except Exception as e:
    print(f"Signup test failed: {e}")

