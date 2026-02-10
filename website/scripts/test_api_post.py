import requests
from requests.auth import HTTPBasicAuth
import sys

def test_api():
    url = "http://localhost:8000/api/v1/posts"
    
    # 1. Test Unauthenticated
    print("Testing unauthenticated access...")
    res = requests.post(url, json={"title": "Unauthorized", "content": "Fail"})
    print(f"Status: {res.status_code} (Expected: 401)")

    # 2. Test Invalid Credentials
    print("\nTesting invalid credentials...")
    res = requests.post(url, json={"title": "Invalid", "content": "Fail"}, auth=HTTPBasicAuth("admin", "wrongpassword"))
    print(f"Status: {res.status_code} (Expected: 401)")

    # 3. Test Valid Creation
    print("\nTesting valid post creation...")
    payload = {
        "title": "Programmatic Deep Space Update",
        "title_it": "Aggiornamento Programmatico dello Spazio Profondo",
        "content": "<p>The James Webb telescope has detected a new nebula.</p>",
        "content_it": "<p>Il telescopio James Webb ha rilevato una nuova nebulosa.</p>",
        "tags": ["astronomy", "api", "automated"],
        "status": "published"
    }
    
    # Using default admin credentials from main.py
    res = requests.post(url, json=payload, auth=HTTPBasicAuth("admin", "mars2026"))
    
    if res.status_code == 200:
        print("✅ Post created successfully!")
        print(f"Response: {res.json()}")
    else:
        print(f"❌ Failed to create post: {res.status_code}")
        print(res.text)

if __name__ == "__main__":
    test_api()
