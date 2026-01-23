# Mood Your Weather - Backend API

Backend RESTful API per l'app **Mood Your Weather**, costruito con FastAPI e Firebase.

## 🚀 Features

- ✅ **Autenticazione completa**: Register, Login, Social Login (Google/Apple), Account Deletion
- ✅ **CRUD Mood Entries**: Creazione, lettura, aggiornamento ed eliminazione dei mood
- ✅ **Statistics & Analytics**: Streak tracking, dominant mood, weekly rhythm, pattern recognition
- ✅ **Weather Integration**: OpenWeatherMap API con caching intelligente
- ✅ **Offline Sync**: Sincronizzazione batch con conflict resolution
- ✅ **Rate Limiting**: Protezione contro abusi (100 req/min per utente)
- ✅ **Firebase Integration**: Authentication e Realtime Database
- 🔧 **NLP Analysis** (Skeleton): Preparato per Google Cloud Natural Language API
- 🔧 **Data Export** (Skeleton): Preparato per export Google Sheets e CSV

## 📋 Requisiti

- Python 3.10+
- Firebase Project con:
  - Authentication abilitato (Email/Password, Google, Apple)
  - Realtime Database configurato
  - Service Account Key JSON
- OpenWeatherMap API Key (free tier)

## 🛠️ Setup

### 1. Clone e Environment

```bash
cd mood-your-weather-BE

# Crea virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# Oppure su Windows: venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt
```

### 2. Configurazione Firebase

1. Vai su [Firebase Console](https://console.firebase.google.com/)
2. Crea un nuovo progetto o usa uno esistente
3. Abilita **Authentication** (Email/Password, Google, Apple)
4. Crea **Realtime Database** (inizia in test mode, poi configura rules)
5. Genera Service Account Key:
   - Project Settings → Service Accounts
   - Generate New Private Key
   - Salva il file JSON nella root del progetto

6. Rinomina il file: `mood-your-weather-firebase-adminsdk-xxxxx.json`

### 3. Environment Variables

Crea/modifica il file `.env`:

```env
OPENWEATHER_API_KEY=your_openweather_api_key_here
FIREBASE_DATABASE_URL=https://your-project-id-default-rtdb.firebaseio.com/
```

**Ottieni OpenWeatherMap API Key:**

- Registrati su [OpenWeatherMap](https://openweathermap.org/api)
- Free tier: 60 calls/min, 1M calls/month

### 4. Firebase Realtime Database Rules

Configura le regole di sicurezza nel Firebase Console:

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "moods": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "stats": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": false
      }
    }
  }
}
```

## 🏃 Run

### Development

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Oppure:

```bash
fastapi dev main.py
```

### Production

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 API Documentation

Una volta avviato il server, visita:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🔐 Autenticazione

### Flow Client-Side (Raccomandato)

1. **Client** usa Firebase Client SDK per login
2. **Client** invia `idToken` al backend negli header:
   ```
   Authorization: Bearer <idToken>
   ```
3. **Backend** verifica token con Firebase Admin SDK

### Test con Custom Token

Per testing, usa l'endpoint `/auth/register` o `/auth/login` che ritorna un custom token.

## 📡 Endpoints Principali

### Authentication (`/auth`)

- `POST /auth/register` - Registrazione nuovo utente
- `POST /auth/login` - Login (genera custom token per test)
- `POST /auth/social-login` - Login con Google/Apple
- `DELETE /auth/user/{userId}` - Cancellazione account (GDPR)
- `GET /auth/verify` - Verifica validità token

### Moods (`/moods`)

- `POST /moods` - Crea nuovo mood entry
- `GET /moods` - Lista moods con filtri (startDate, endDate, limit, offset)
- `GET /moods/{entryId}` - Dettaglio mood
- `PUT /moods/{entryId}` - Aggiorna mood
- `DELETE /moods/{entryId}` - Elimina mood

### Statistics (`/stats`)

- `GET /stats/user/{userId}` - Statistiche aggregate
- `GET /stats/calendar/{userId}?year=2026&month=1` - Calendario mensile
- `POST /stats/recalculate/{userId}` - Forza ricalcolo statistiche

### Weather (`/weather`)

- `GET /weather/current?lat=45.46&lon=9.19` - Meteo attuale (cached 10 min)

### Sync (`/sync`)

- `POST /sync` - Sincronizzazione batch (max 100 entries)
- `GET /sync/status/{userId}` - Stato sincronizzazione

### NLP & Export (Skeletons)

- `POST /nlp/analyze` - Analisi sentiment (mock)
- `POST /export/google-sheets` - Export Google Sheets (not implemented)
- `POST /export/csv` - Export CSV (not implemented)

## 🏗️ Architettura

```
mood-your-weather-BE/
├── main.py                 # FastAPI app principale
├── firebase_config.py      # Configurazione Firebase
├── models.py               # Modelli Pydantic
├── requirements.txt        # Dipendenze Python
├── .env                    # Environment variables
│
├── middleware/
│   ├── __init__.py
│   └── auth.py            # JWT verification, rate limiting
│
├── services/
│   ├── __init__.py
│   └── firebase_service.py # Operazioni Firebase DB
│
└── routers/
    ├── __init__.py
    ├── auth.py            # Autenticazione
    ├── moods.py           # CRUD moods
    ├── stats.py           # Statistics & analytics
    ├── weather.py         # OpenWeatherMap integration
    ├── sync.py            # Offline sync
    ├── nlp.py             # NLP skeleton
    └── export.py          # Export skeleton
```

## 📊 Data Model

### Firebase Realtime Database Structure

```
/users/{userId}
  ├── email: string
  ├── name: string
  ├── createdAt: timestamp
  └── settings: {...}

/moods/{userId}/{entryId}
  ├── entryId: string
  ├── userId: string
  ├── timestamp: timestamp
  ├── emojis: ["sunny", "partly", ...]
  ├── intensity: number (0-100)
  ├── note: string (optional)
  ├── location: { lat, lon } (optional)
  ├── externalWeather: {...} (optional)
  ├── createdAt: timestamp
  └── updatedAt: timestamp (optional)

/stats/{userId}
  ├── totalEntries: number
  ├── currentStreak: number
  ├── longestStreak: number
  ├── dominantMood: string
  ├── averageIntensity: number
  ├── weeklyRhythm: { monday: 65, tuesday: 72, ... }
  └── lastUpdated: timestamp
```

## 🔒 Sicurezza

- ✅ JWT token verification via Firebase Admin SDK
- ✅ Rate limiting: 100 requests/min per utente
- ✅ Ownership validation su tutte le risorse
- ✅ Input validation con Pydantic
- ✅ CORS configurato per mobile app
- ✅ GDPR compliant (delete account endpoint)

## 🧪 Testing

### Manual Testing con Swagger UI

Visita http://localhost:8000/docs e testa tutti gli endpoints interattivamente.

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Register user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get weather
curl "http://localhost:8000/weather/current?lat=45.46&lon=9.19"
```

## 📈 Performance

- **Response Time**: < 200ms per endpoint read
- **Rate Limiting**: 100 req/min per utente
- **Weather Cache**: 10 minuti (rispetta free tier limits)
- **Async Operations**: Tutte le operazioni I/O sono async

## 🔮 Future Implementations

### 1. Google Cloud NLP (`/nlp`)

- Analisi sentiment delle note
- Suggerimento emoji basato su sentiment
- Entity extraction per pattern recognition

### 2. Google Sheets Export (`/export`)

- OAuth 2.0 flow per authorization
- Creazione spreadsheet con formattazione
- Auto-update per dati live

### 3. Background Jobs

- Daily streak reset (cron job)
- Pattern recognition ML model
- Push notifications intelligenti

## 🐛 Troubleshooting

**Firebase Connection Error:**

```
Verificare FIREBASE_DATABASE_URL in .env
Controllare service account JSON
```

**OpenWeatherMap 401:**

```
Verificare OPENWEATHER_API_KEY in .env
Attivare API key su openweathermap.org
```

**Import Errors:**

```bash
pip install -r requirements.txt --force-reinstall
```

## 📝 License

Proprietario - Mood Your Weather Project

---

**Made with ❤️ and ☁️ by Mood Your Weather Team**
