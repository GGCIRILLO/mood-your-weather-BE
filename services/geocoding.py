import os
import httpx
from typing import Optional
from pydantic import BaseModel
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Configurazione
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")
OPENCAGE_BASE_URL = "https://api.opencagedata.com/geocode/v1/json"
REQUEST_TIMEOUT = 5.0  # secondi


class GeocodedLocation(BaseModel):
    """Risultato del reverse geocoding"""
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    formatted: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "Milan",
                "neighborhood": "Centro Storico",
                "state": "Lombardia",
                "country": "Italy",
                "country_code": "it",
                "formatted": "Centro Storico, 20121 Milan, Italy"
            }
        }


@lru_cache(maxsize=1000)
def _get_cache_key(lat: float, lon: float) -> str:
    """
    Genera cache key con coordinate arrotondate (precisione ~100m)
    LRU cache evita chiamate duplicate per stesse location
    """
    return f"{round(lat, 3)},{round(lon, 3)}"


async def reverse_geocode(
    latitude: float, 
    longitude: float
) -> Optional[GeocodedLocation]:
    """
    Converte coordinate GPS in indirizzo leggibile usando OpenCage API
    
    Args:
        latitude: Latitudine
        longitude: Longitudine
    
    Returns:
        GeocodedLocation con city, neighborhood, etc. o None se fallisce
    
    Example:
        >>> location = await reverse_geocode(45.4642, 9.1900)
        >>> print(location.city)  # "Milan"
        >>> print(location.neighborhood)  # "Centro Storico"
    """
    
    # Check cache implicito via lru_cache su _get_cache_key
    cache_key = _get_cache_key(latitude, longitude)
    logger.info(f"Geocoding request for {cache_key}")
    
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                OPENCAGE_BASE_URL,
                params={
                    "q": f"{latitude},{longitude}",
                    "key": OPENCAGE_API_KEY,
                    "language": "en",  # Usa 'it' per italiano
                    "no_annotations": 1,  # Riduce response size
                    "limit": 1,
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                logger.warning(f"No geocoding results for {latitude},{longitude}")
                return None
            
            result = data["results"][0]
            components = result.get("components", {})
            
            return GeocodedLocation(
                city=components.get("city") or components.get("town") or components.get("village"),
                neighborhood=components.get("neighbourhood"),
                suburb=components.get("suburb"),
                state=components.get("state") or components.get("region"),
                country=components.get("country"),
                country_code=components.get("country_code"),
                formatted=result.get("formatted", "Unknown location")
            )
    
    except httpx.TimeoutException:
        logger.error(f"Geocoding timeout for {latitude},{longitude}")
        return None
    
    except httpx.HTTPStatusError as e:
        logger.error(f"Geocoding HTTP error: {e.response.status_code}")
        return None
    
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        return None


def format_location_short(location: GeocodedLocation) -> str:
    """
    Formatta location in stringa breve per UI
    
    Logica:
    - Se c'è neighborhood: "Neighborhood, City"
    - Se solo city: "City, Country"
    - Fallback: primi 2 elementi del formatted
    
    Example:
        >>> format_location_short(location)
        "Centro Storico, Milan"
    """
    parts = []
    
    # Priorità: neighborhood > suburb > city
    if location.neighborhood:
        parts.append(location.neighborhood)
    elif location.suburb:
        parts.append(location.suburb)
    
    if location.city:
        parts.append(location.city)
    
    # Se non abbiamo abbastanza info, usa formatted
    if not parts:
        parts = location.formatted.split(",")[:2]
    
    return ", ".join(parts).strip()


def format_location_full(location: GeocodedLocation) -> str:
    """
    Formatta location in stringa completa
    
    Example:
        >>> format_location_full(location)
        "Centro Storico, 20121 Milan, Italy"
    """
    return location.formatted
