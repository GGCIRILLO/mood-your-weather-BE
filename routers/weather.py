"""
Router per integrazione OpenWeatherMap API
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import Optional
import httpx
import os
import logging
from datetime import datetime, timedelta, timezone
from models import WeatherCurrent, Location, ExternalWeather
from middleware.auth import optional_auth
from services.geocoding import reverse_geocode, format_location_short

# Setup logger
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/weather", tags=["Weather"])


# Cache semplice in-memory (in produzione usare Redis)
weather_cache = {}
CACHE_DURATION = timedelta(minutes=10)  # Cache per 10 minuti


def get_cache_key(lat: float, lon: float) -> str:
    """Genera chiave cache da coordinate"""
    return f"{round(lat, 2)}:{round(lon, 2)}"


async def fetch_openweather_data(lat: float, lon: float) -> dict:
    """Fetch dati da OpenWeatherMap API"""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather service not configured"
        )
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",  # Celsius
        "lang": "en"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return response.json()
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Weather API authentication failed"
            )
        elif e.response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Weather API rate limit exceeded"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Weather API error: {e.response.status_code}"
            )
    
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Weather API request timeout"
        )
    

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch weather data: {str(e)}"
        )


async def fetch_and_parse_weather(lat: float, lon: float) -> Optional[ExternalWeather]:
    """
    Fetch weather data and parse into ExternalWeather model.
    Returns None on error to avoid blocking mood creation.
    """
    try:
        # Check cache (reuse existing cache logic if possible, or simplified for this use case)
        cache_key = get_cache_key(lat, lon)
        now = datetime.utcnow()
        
        if cache_key in weather_cache:
            cached_data, cached_time = weather_cache[cache_key]
            # Cached data is the raw dict from WeatherCurrent.model_dump()
            # We need to extract fields for ExternalWeather
            if now - cached_time < CACHE_DURATION:
                # We have a full WeatherCurrent dict, map it to ExternalWeather
                return ExternalWeather(
                    temp=cached_data['temp'],
                    feels_like=cached_data['feels_like'],
                    humidity=cached_data['humidity'],
                    weather_main=cached_data['weather_main'],
                    weather_description=cached_data['weather_description'],
                    icon=cached_data['icon']
                )

        # Fetch fresh data
        weather_data = await fetch_openweather_data(lat, lon)
        
        # Parse relevant fields
        external_weather = ExternalWeather(
            temp=weather_data['main']['temp'],
            feels_like=weather_data['main']['feels_like'],
            humidity=weather_data['main']['humidity'],
            weather_main=weather_data['weather'][0]['main'],
            weather_description=weather_data['weather'][0]['description'],
            icon=weather_data['weather'][0]['icon']
        )
        
        # We assume the main get_current_weather endpoint will handle its own caching 
        # when called directly. Since we are reusing fetch_openweather_data which returns raw JSON,
        # we can optionally update cache here too if we want full consistency, 
        # but technically we only need the ExternalWeather subset here.
        # For simplicity and to avoid side effects on the main cache structure (which stores WeatherCurrent),
        # we won't write to the global cache here unless we reconstruct the full object, 
        # which requires more parsing.
        
        return external_weather

    except Exception as e:
        logger.error(f"Error fetching weather for mood: {str(e)}")
        return None


@router.get("/current", response_model=WeatherCurrent)
async def get_current_weather(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    user: Optional[dict] = Depends(optional_auth)
):
    """
    Meteo attuale per location
    
    - Integrazione con OpenWeatherMap API
    - Caching per 10 minuti per rispettare rate limits
    - Non richiede autenticazione (ma logged users hanno priorità)
    """
    try:
        # Check cache
        cache_key = get_cache_key(lat, lon)
        now = datetime.now(timezone.utc)

        if cache_key in weather_cache:
            cached_data, cached_time = weather_cache[cache_key]
            if now - cached_time < CACHE_DURATION:
                return WeatherCurrent(**cached_data)
        
        # Fetch fresh data
        weather_data = await fetch_openweather_data(lat, lon)
        
        # Reverse geocoding for human-readable name
        location_name = None
        geocoded = await reverse_geocode(lat, lon)
        if geocoded:
            location_name = format_location_short(geocoded)

        # Parse response
        weather_current = WeatherCurrent(
            location=Location(lat=lat, lon=lon, name=location_name),
            temp=weather_data['main']['temp'],
            feels_like=weather_data['main']['feels_like'],
            temp_min=weather_data['main']['temp_min'],
            temp_max=weather_data['main']['temp_max'],
            pressure=weather_data['main']['pressure'],
            humidity=weather_data['main']['humidity'],
            weather_main=weather_data['weather'][0]['main'],
            weather_description=weather_data['weather'][0]['description'],
            icon=weather_data['weather'][0]['icon'],
            wind_speed=weather_data['wind']['speed'],
            clouds=weather_data['clouds']['all'],
            dt=datetime.fromtimestamp(weather_data['dt']),
            sunrise=datetime.fromtimestamp(weather_data['sys']['sunrise']),
            sunset=datetime.fromtimestamp(weather_data['sys']['sunset']),
            timezone=weather_data['timezone']
        )
        
        # Update cache
        weather_cache[cache_key] = (weather_current.model_dump(), now)
        
        # Cleanup old cache entries (keep max 100)
        if len(weather_cache) > 100:
            oldest_key = min(weather_cache.items(), key=lambda x: x[1][1])[0]
            del weather_cache[oldest_key]
        
        return weather_current
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete("/cache", status_code=status.HTTP_204_NO_CONTENT)
async def clear_weather_cache():
    """
    Pulisci cache meteo (admin endpoint)
    In produzione dovrebbe richiedere autenticazione admin
    """
    weather_cache.clear()
    return None
