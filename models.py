"""
Modelli Pydantic per validazione e serializzazione dati
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class MoodEmoji(str, Enum):
    """Emoji disponibili per rappresentare il mood"""
    SUNNY = "sunny"
    PARTLY = "partly"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"


class AuthProvider(str, Enum):
    """Provider di autenticazione sociale"""
    GOOGLE = "google"
    APPLE = "apple"


# ==================== Auth Models ====================

class UserRegister(BaseModel):
    """Modello per registrazione utente"""
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password minimo 6 caratteri")
    name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Modello per login utente"""
    email: EmailStr
    password: str


class SocialLogin(BaseModel):
    """Modello per login sociale"""
    provider: AuthProvider
    idToken: str = Field(..., description="Token ID da provider (Google/Apple)")


class AuthResponse(BaseModel):
    """Risposta autenticazione"""
    userId: str
    token: str
    email: Optional[str] = None
    name: Optional[str] = None


# ==================== Mood Models ====================

class Location(BaseModel):
    """Coordinata geografica"""
    lat: float = Field(..., ge=-90, le=90, description="Latitudine")
    lon: float = Field(..., ge=-180, le=180, description="Longitudine")


class ExternalWeather(BaseModel):
    """Dati meteo esterni da OpenWeatherMap"""
    temp: float
    feels_like: float
    humidity: int
    weather_main: str  # "Clear", "Clouds", "Rain", etc.
    weather_description: str
    icon: str


class MoodCreate(BaseModel):
    """Creazione nuovo mood entry"""
    userId: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    emojis: List[str] = Field(..., min_length=1, max_length=5)
    intensity: int = Field(..., ge=0, le=100, description="Intensità mood 0-100")
    note: Optional[str] = Field(None, max_length=500)
    location: Optional[Location] = None
    
    @validator('emojis')
    def validate_emojis(cls, v):
        """Rimuovi duplicati e valida che siano emoji valide"""
        valid_emojis = [e.value for e in MoodEmoji]
        for emoji in v:
            if emoji not in valid_emojis:
                raise ValueError(f"Invalid emoji: {emoji}. Must be one of {valid_emojis}")
        return list(dict.fromkeys(v))  # Mantiene ordine, rimuove duplicati


class MoodUpdate(BaseModel):
    """Aggiornamento mood entry esistente"""
    emojis: Optional[List[str]] = Field(None, min_length=1, max_length=5)
    intensity: Optional[int] = Field(None, ge=0, le=100)
    note: Optional[str] = Field(None, max_length=500)
    
    @validator('emojis')
    def validate_emojis(cls, v):
        if v is not None:
            valid_emojis = [e.value for e in MoodEmoji]
            for emoji in v:
                if emoji not in valid_emojis:
                    raise ValueError(f"Invalid emoji: {emoji}. Must be one of {valid_emojis}")
            return list(dict.fromkeys(v))
        return v


class MoodEntry(BaseModel):
    """Mood entry completo (dal database)"""
    entryId: str
    userId: str
    timestamp: datetime
    emojis: List[str]
    intensity: int
    note: Optional[str] = None
    location: Optional[Location] = None
    externalWeather: Optional[ExternalWeather] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MoodList(BaseModel):
    """Lista paginata di mood entries"""
    items: List[MoodEntry]
    total: int
    limit: int
    offset: int
    hasMore: bool


# ==================== Statistics Models ====================

class WeeklyRhythm(BaseModel):
    """Ritmo settimanale dei mood"""
    monday: float
    tuesday: float
    wednesday: float
    thursday: float
    friday: float
    saturday: float
    sunday: float


class MoodPattern(BaseModel):
    """Pattern riconosciuti nell'umore"""
    pattern_type: str  # "time_of_day", "weekday", "weather_correlation"
    description: str
    confidence: float = Field(..., ge=0, le=1)
    occurrences: int


class UserStats(BaseModel):
    """Statistiche aggregate utente"""
    totalEntries: int
    currentStreak: int
    longestStreak: int
    dominantMood: Optional[str] = None
    averageIntensity: float
    weeklyRhythm: Optional[WeeklyRhythm] = None
    patterns: List[MoodPattern] = []
    lastUpdated: datetime


class CalendarDay(BaseModel):
    """Dati mood per un giorno nel calendario"""
    emojis: List[str]
    intensity: int
    hasNote: bool = False


class CalendarMonth(BaseModel):
    """Dati calendario per un mese"""
    year: int
    month: int
    days: Dict[str, CalendarDay]  # { "2026-01-15": {...}, ... }


# ==================== Weather Models ====================

class WeatherCurrent(BaseModel):
    """Meteo attuale"""
    location: Location
    temp: float
    feels_like: float
    temp_min: float
    temp_max: float
    pressure: int
    humidity: int
    weather_main: str
    weather_description: str
    icon: str
    wind_speed: float
    clouds: int
    dt: datetime
    sunrise: datetime
    sunset: datetime
    timezone: int


# ==================== NLP Models (Skeleton) ====================

class NLPAnalyzeRequest(BaseModel):
    """Richiesta analisi sentiment (skeleton)"""
    text: str = Field(..., max_length=1000)


class NLPAnalyzeResponse(BaseModel):
    """Risposta analisi sentiment (skeleton)"""
    sentiment: str  # "positive", "negative", "neutral"
    score: float = Field(..., ge=-1, le=1)
    magnitude: float
    emojis_suggested: List[str] = []


# ==================== Export Models (Skeleton) ====================

class ExportRequest(BaseModel):
    """Richiesta export dati (skeleton)"""
    userId: str
    format: str = Field(default="google_sheets", pattern="^(google_sheets|csv|json)$")
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None


class ExportResponse(BaseModel):
    """Risposta export (skeleton)"""
    success: bool
    url: Optional[str] = None  # URL Google Sheet o file download
    message: str


# ==================== Sync Models ====================

class SyncMoodEntry(BaseModel):
    """Mood entry per sincronizzazione (da client)"""
    localId: str  # ID temporaneo generato dal client
    userId: str
    timestamp: datetime
    emojis: List[str]
    intensity: int
    note: Optional[str] = None
    location: Optional[Location] = None
    clientTimestamp: datetime  # Timestamp quando entry è stato creato sul client


class SyncRequest(BaseModel):
    """Richiesta sincronizzazione batch"""
    entries: List[SyncMoodEntry] = Field(..., max_length=100)


class SyncResult(BaseModel):
    """Risultato sincronizzazione per singolo entry"""
    localId: str
    serverId: Optional[str] = None  # ID assegnato dal server
    status: str  # "created", "updated", "conflict", "error"
    serverTimestamp: Optional[datetime] = None
    message: Optional[str] = None


class SyncResponse(BaseModel):
    """Risposta sincronizzazione batch"""
    results: List[SyncResult]
    totalProcessed: int
    successCount: int
    errorCount: int


# ==================== Forecast Models (Skeleton) ====================

class MoodForecast(BaseModel):
    """Previsione mood futuri (skeleton)"""
    date: datetime
    predicted_mood: str
    confidence: float = Field(..., ge=0, le=1)
    factors: List[str] = []  # ["weather_pattern", "time_of_week", "historical_trend"]


class ForecastResponse(BaseModel):
    """Risposta forecast (skeleton)"""
    userId: str
    forecasts: List[MoodForecast]
    ml_model_version: str = "v1.0"  # Rinominato da model_version per evitare conflitto
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Error Models ====================

class ErrorResponse(BaseModel):
    """Risposta errore standard"""
    error: str
    detail: Optional[str] = None
    status_code: int
