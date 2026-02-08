"""
Router per statistiche e analytics
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone
from models import UserStats, CalendarMonth, CalendarDay
from services.firebase_service import firebase_service
from middleware.auth import get_current_user_id, check_rate_limit


router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/user/{userId}", response_model=UserStats)
async def get_user_stats(
    userId: str,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Statistiche aggregate per utente
    
    Include:
    - Total entries, current/longest streak
    - Dominant mood, average intensity
    - Weekly rhythm (media intensità per giorno)
    - Pattern riconosciuti (placeholder per ML futuro)
    """
    # Verifica ownership
    if userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own statistics"
        )
    
    try:
        stats = await firebase_service.get_user_stats(userId)
        
        if not stats:
            # Ritorna statistiche vuote se utente non ha mood entries
            return UserStats(
                totalEntries=0,
                currentStreak=0,
                longestStreak=0,
                dominantMood=None,
                averageIntensity=0.0,
                weeklyRhythm=None,
                patterns=[],
                lastUpdated=datetime.now(timezone.utc)
            )

        return UserStats(**stats)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


@router.get("/calendar/{userId}", response_model=CalendarMonth)
async def get_calendar_data(
    userId: str,
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Dati calendario mensile
    
    Ritorna dizionario con entry per ogni giorno del mese che ha mood data:
    {
        "2026-01-15": { "emojis": ["sunny"], "intensity": 75, "hasNote": true },
        "2026-01-16": { ... }
    }
    """
    # Verifica ownership
    if userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own calendar"
        )
    
    try:
        calendar_data_raw = await firebase_service.get_calendar_data(userId, year, month)
        
        # Converti dict raw in CalendarDay objects
        calendar_days = {}
        for date_key, day_data in calendar_data_raw.items():
            calendar_days[date_key] = CalendarDay(**day_data)
        
        return CalendarMonth(
            year=year,
            month=month,
            days=calendar_days
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendar data: {str(e)}"
        )


@router.post("/recalculate/{userId}", status_code=status.HTTP_202_ACCEPTED)
async def recalculate_stats(
    userId: str,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Forza ricalcolo statistiche utente
    
    Utile dopo import batch o correzioni dati
    """
    # Verifica ownership
    if userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only recalculate your own statistics"
        )
    
    try:
        await firebase_service.update_user_stats(userId)
        
        return {
            "message": "Statistics recalculation started",
            "userId": userId
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recalculate statistics: {str(e)}"
        )
