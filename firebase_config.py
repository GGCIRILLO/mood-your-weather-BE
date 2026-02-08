import firebase_admin
from firebase_admin import credentials, db, auth
import os
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

def initialize_firebase():
    """Inizializza Firebase se non già fatto"""
    if not firebase_admin._apps:
        # Path al file delle credenziali
        cred_path = os.path.join(
            os.path.dirname(__file__), 
            "mood-your-weather-firebase-adminsdk-fbsvc-da13f7ee3e.json"
        )
        
        # Verifica che il file esista
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Firebase credentials file not found: {cred_path}")
        
        # Inizializza Firebase Admin SDK
        cred = credentials.Certificate(cred_path)
        
        # Leggi database URL da .env
        database_url = os.getenv('FIREBASE_DATABASE_URL')
        if not database_url:
            raise ValueError("FIREBASE_DATABASE_URL not found in environment variables")

        firebase_admin.initialize_app(cred, {
            'databaseURL': database_url
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
