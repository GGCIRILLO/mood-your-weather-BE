from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from models import Challenge, ChallengeStatus, UserChallengesResponse
from services.firebase_service import firebase_service
from middleware.auth import get_current_user_id

router = APIRouter(prefix="/challenges", tags=["Challenges"])

CHALLENGES_METADATA = [
    {
        "id": "7_day_streak",
        "name": "7-Day Streak",
        "goal": "Log your mood for 7 consecutive days.",
        "description": "Build a consistent habit to unlock your weekly emotional weather report.",
        "icon": "vibrant_sun",
        "targetValue": 7
    },
    {
        "id": "storyteller",
        "name": "Storyteller",
        "goal": "Add a text note to any mood entry.",
        "description": "Provide qualitative context to your 'inner climate' to enrich your mood analysis.",
        "icon": "book_open",
        "targetValue": 1
    },
    {
        "id": "mindful_moment",
        "name": "Mindful Moment",
        "goal": "Complete one guided breathing exercise or meditation.",
        "description": "Use the practice player to find calm and check your mood again after the session.",
        "icon": "wind_wave",
        "targetValue": 1
    },
    {
        "id": "weather_mixologist",
        "name": "Weather Mixologist",
        "goal": "Combine two different weather emojis in a single mood entry.",
        "description": "Use the drag-and-drop canvas to show that emotions can be complex, like a 'sunny but cloudy' day.",
        "icon": "flask",
        "targetValue": 1
    }
]

@router.get("", response_model=UserChallengesResponse)
async def get_challenges(current_user_id: str = Depends(get_current_user_id)):
    """Ottieni lo stato delle sfide dell'utente"""
    try:
        stats = await firebase_service.get_user_stats(current_user_id)
        if stats is None:
            stats = {}
            
        unlocked_badges = stats.get('unlockedBadges', [])
        current_streak = stats.get('currentStreak', 0)
        mindful_count = stats.get('mindfulMomentsCount', 0)
        
        # Per Storyteller e Weather Mixologist ricalcoliamo il currentValue se non sbloccati
        has_note = "storyteller" in unlocked_badges
        has_mixed_weather = "weather_mixologist" in unlocked_badges
        
        if not has_note or not has_mixed_weather:
            moods, _ = await firebase_service.get_mood_entries(current_user_id, limit=500)
            if not has_note:
                has_note = any(mood.get('note') and str(mood.get('note')).strip() for mood in moods)
            if not has_mixed_weather:
                has_mixed_weather = any(len(mood.get('emojis', [])) >= 2 for mood in moods)
        
        challenges_results = []
        
        for meta in CHALLENGES_METADATA:
            current_value = 0
            if meta['id'] == '7_day_streak':
                current_value = current_streak
            elif meta['id'] == 'storyteller':
                current_value = 1 if has_note else 0
            elif meta['id'] == 'mindful_moment':
                current_value = mindful_count
            elif meta['id'] == 'weather_mixologist':
                current_value = 1 if has_mixed_weather else 0
                
            target = meta['targetValue']
            progress = min(100, int((current_value / target) * 100))
            
            # Use stored unlocked status or current completion
            is_completed = (meta['id'] in unlocked_badges) or (current_value >= target)
            status_val = ChallengeStatus.COMPLETED if is_completed else ChallengeStatus.LOCKED
            
            challenges_results.append(Challenge(
                id=meta['id'],
                name=meta['name'],
                description=meta['description'],
                goal=meta['goal'],
                icon=meta['icon'],
                status=status_val,
                progress=progress,
                currentValue=current_value,
                targetValue=target
            ))
                
        return UserChallengesResponse(
            currentStreak=current_streak,
            unlockedBadges=unlocked_badges,
            challenges=challenges_results
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch challenges: {str(e)}"
        )

@router.post("/mindful", status_code=status.HTTP_200_OK)
async def complete_mindful_moment(current_user_id: str = Depends(get_current_user_id)):
    """Registra il completamento di una sessione di mindfulness"""
    try:
        await firebase_service.increment_mindful_moments(current_user_id)
        return {"message": "Mindful moment recorded successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record mindful moment: {str(e)}"
        )