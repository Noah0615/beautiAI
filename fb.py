# fb.py
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Point to your service account file (or use GOOGLE_APPLICATION_CREDENTIALS env var)
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT", "keys/key.json")

# Initialize app once (module import side-effect is fine for Flask)
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

def get_db():
    return firestore.client()