import firebase_admin
from firebase_admin import credentials, db, auth
import os



def initialize_firebase():
    """Inizializza Firebase se non già fatto"""
    if not firebase_admin._apps:
        # Inizializza Firebase Admin SDK
        cred = credentials.Certificate("mood-your-weather-firebase-adminsdk-fbsvc-da13f7ee3e.json")

        firebase_admin.initialize_app(cred, {
            'databaseURL': "https://mood-your-weather-default-rtdb.europe-west1.firebasedatabase.app/"
        })
        print("✅ Firebase initialized successfully")
    else:
        print("⚠️ Firebase already initialized")

# Chiamalo all'avvio dell'app
initialize_firebase()

# Reference al database
def get_db():
    """Ritorna il reference al Firebase Realtime Database"""
    return db.reference()
