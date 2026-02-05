"""
Router per notifiche e promemoria
"""
from fastapi import APIRouter, HTTPException, status, Depends, Body
from pydantic import BaseModel
from typing import Optional
from middleware.auth import get_current_user_id
from services.firebase_service import firebase_service
import logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class FCMTokenRequest(BaseModel):
    token: str

@router.post("/register", status_code=status.HTTP_200_OK)
async def register_fcm_token(
    request: FCMTokenRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Registra token FCM per l'utente corrente
    Da chiamare all'avvio dell'app mobile o quando il token cambia
    """
    try:
        await firebase_service.save_fcm_token(current_user_id, request.token)
        return {"message": "Token registered successfully"}
    except Exception as e:
        logger.error(f"Failed to register FCM token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register token"
        )

@router.post("/test", status_code=status.HTTP_200_OK)
async def test_notification(
    current_user_id: str = "test_user_verifying" # Depends(get_current_user_id)
):
    """
    Invia una notifica di test all'utente corrente
    """
    try:
        token = await firebase_service.get_fcm_token(current_user_id)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FCM token not found for user"
            )
            
        success = await firebase_service.send_push_notification(
            token=token,
            title="Mood Test",
            body="If you can see this, notifications are working! 🚀"
        )
        
        if not success:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send notification via FCM"
            )
            
        return {"message": "Notification sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test notification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test failed: {str(e)}"
        )

@router.post("/reminders/send", status_code=status.HTTP_200_OK)
async def send_daily_reminders(
    # In production, secure this with an Admin Key check or similar
    # admin_key: str = Depends(verify_admin_key)
    target_user_id: Optional[str] = None
):
    """
    Trigger invio promemoria giornalieri
    
    Se target_user_id è specificato, invia solo a quell'utente (utile per test/cron specifici).
    Altrimenti, questo endpoint dovrebbe iterare su tutti gli utenti (logica complessa su Firebase Realtime DB).
    
    Logica:
    - Se l'utente non ha loggato oggi:
        - Se ha uno streak attivo (>0): "🔥 Keep your 7-day streak alive!"
        - Altrimenti: "⏰ Time to track your mood!"
    """
    if not target_user_id:
        return {
             "message": "Please provide target_user_id for now. Batch iteration requires dedicated worker.",
             "status": "skipped"
        }

    try:
        # 1. Get Token
        token = await firebase_service.get_fcm_token(target_user_id)
        if not token:
             return {"message": f"No token for user {target_user_id}", "status": "skipped"}

        # 2. Get Stats to check last activity
        stats = await firebase_service.get_user_stats(target_user_id)
        if not stats:
             # No stats implies no activity ever, send welcome/daily?
             await firebase_service.send_push_notification(
                token=token,
                title="Mood Tracker",
                body="⏰ Time to track your first mood!"
            )
             return {"message": "Sent first reminder", "status": "sent"}

        # 3. Check if logged today
        last_updated_str = stats.get('lastUpdated')
        if not last_updated_str:
             # Should not happen if stats exist
             return {"message": "Invalid stats", "status": "error"}
             
        from datetime import datetime, timezone
        last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
        today = datetime.now(timezone.utc).date()
        
        if last_updated.date() < today:
            # Not logged today
            current_streak = stats.get('currentStreak', 0)
            
            if current_streak > 0:
                 # Streak Saver
                 await firebase_service.send_push_notification(
                    token=token,
                    title="Streak Alert! 🔥",
                    body=f"Keep your {current_streak}-day streak alive!"
                )
                 msg = "Sent streak reminder"
            else:
                 # Standard Reminder
                 await firebase_service.send_push_notification(
                    token=token,
                    title="Mood Reminder ⏰",
                    body="Time to track your mood!"
                )
                 msg = "Sent daily reminder"
            
            return {"message": msg, "user_id": target_user_id, "status": "sent"}
            
        else:
            return {"message": "User already logged today", "user_id": target_user_id, "status": "skipped"}

    except Exception as e:
        logger.error(f"Reminder trigger failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reminder failed: {str(e)}"
        )
