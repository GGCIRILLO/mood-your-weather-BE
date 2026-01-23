import firebase_admin
from firebase_admin import credentials, db, auth
import os

# Inizializza Firebase Admin SDK
cred = credentials.Certificate("mood-your-weather-firebase-adminsdk-fbsvc-da13f7ee3e.json")

# URL del Realtime Database - modifica con il tuo project ID
DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://mood-your-weather-default-rtdb.firebaseio.com/")

firebase_admin.initialize_app(cred, {
    'databaseURL': DATABASE_URL
})

# Reference al database
def get_db():
    """Ritorna il reference al Firebase Realtime Database"""
    return db.reference()
