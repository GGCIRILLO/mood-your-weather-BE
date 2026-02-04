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
):
    """
    Trigger invio promemoria giornalieri (Skeleton)
    
    Questo endpoint dovrebbe essere chiamato da un job schedulato (es. CRON).
    Per ora, simula l'invio inviando una notifica generica agli utenti che hanno un token.
    
    NOTA: In un'app reale, itereremmo su tutti gli utenti e controlleremmo se hanno loggato oggi.
    Per semplicità, questo è uno stub che dimostra il concetto.
    """
    # TODO: Fetch all users with tokens > Check mood today > Send
    # Since we don't have a "get all users" efficient query easily without scanning firebase,
    # we will just return a message saying this requires external scheduler logic.
    
    return {
        "message": "Daily reminder trigger endpoint ready. Logic to iterate users pending implementation.",
        "note": "Call POST /notifications/test to verify connectivity first."
    }
