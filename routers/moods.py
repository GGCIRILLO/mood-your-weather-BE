"""
Router per CRUD mood entries
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
from models import MoodCreate, MoodUpdate, MoodEntry, MoodList
from services.firebase_service import firebase_service
from middleware.auth import get_current_user_id, check_rate_limit


router = APIRouter(prefix="/moods", tags=["Moods"])


@router.post("", response_model=MoodEntry, status_code=status.HTTP_201_CREATED)
async def create_mood(
    mood_data: MoodCreate,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Crea nuovo mood entry
    
    - Salva nel Firebase Realtime Database
    - Trigger aggiornamento statistiche in background
    - Supporta location opzionale per correlazione meteo
    """
    # Verifica ownership
    if mood_data.userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create moods for yourself"
        )
    
    try:
        # Converti in dict per Firebase
        mood_dict = mood_data.model_dump()
        
        # Crea entry
        entry_id = await firebase_service.create_mood_entry(mood_dict)
        
        # Recupera entry completo
        created_mood = await firebase_service.get_mood_entry(current_user_id, entry_id)
        
        if not created_mood:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created mood"
            )
        
        return MoodEntry(**created_mood)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mood: {str(e)}"
        )


@router.get("", response_model=MoodList)
async def get_moods(
    userId: Optional[str] = Query(None, description="Filter by user ID"),
    startDate: Optional[datetime] = Query(None, description="Start date filter (ISO-8601)"),
    endDate: Optional[datetime] = Query(None, description="End date filter (ISO-8601)"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Lista mood entries con filtri e paginazione
    
    - Filtra per data range
    - Paginazione con limit/offset
    - Richiede autenticazione
    - Può vedere solo i propri moods
    """
    # Se userId non specificato, usa current user
    target_user_id = userId or current_user_id
    
    # Verifica ownership
    if target_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own moods"
        )
    
    try:
        moods_data, total = await firebase_service.get_mood_entries(
            user_id=target_user_id,
            start_date=startDate,
            end_date=endDate,
            limit=limit,
            offset=offset
        )
        
        # Converti in MoodEntry objects
        mood_entries = [MoodEntry(**mood) for mood in moods_data]
        
        return MoodList(
            items=mood_entries,
            total=total,
            limit=limit,
            offset=offset,
            hasMore=(offset + limit) < total
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch moods: {str(e)}"
        )


@router.get("/{entryId}", response_model=MoodEntry)
async def get_mood(
    entryId: str,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Dettaglio singolo mood entry
    
    - Verifica ownership
    - Richiede autenticazione
    """
    try:
        mood = await firebase_service.get_mood_entry(current_user_id, entryId)
        
        if not mood:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mood entry not found"
            )
        
        # Verifica ownership
        if mood.get('userId') != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this mood entry"
            )
        
        return MoodEntry(**mood)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch mood: {str(e)}"
        )


@router.put("/{entryId}", response_model=MoodEntry)
async def update_mood(
    entryId: str,
    update_data: MoodUpdate,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Aggiorna mood entry esistente
    
    - Può modificare: emojis, intensity, note
    - Verifica ownership
    - Richiede autenticazione
    """
    try:
        # Verifica esistenza e ownership
        existing_mood = await firebase_service.get_mood_entry(current_user_id, entryId)
        
        if not existing_mood:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mood entry not found"
            )
        
        if existing_mood.get('userId') != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this mood entry"
            )
        
        # Prepara dati per update (solo campi non-None)
        update_dict = update_data.model_dump(exclude_none=True)
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Aggiorna
        success = await firebase_service.update_mood_entry(
            current_user_id,
            entryId,
            update_dict
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update mood"
            )
        
        # Recupera mood aggiornato
        updated_mood = await firebase_service.get_mood_entry(current_user_id, entryId)
        
        if not updated_mood:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated mood"
            )
        
        return MoodEntry(**updated_mood)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mood: {str(e)}"
        )


@router.delete("/{entryId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mood(
    entryId: str,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Elimina mood entry
    
    - Verifica ownership
    - Aggiorna statistiche automaticamente
    - Richiede autenticazione
    """
    try:
        # Verifica esistenza e ownership
        existing_mood = await firebase_service.get_mood_entry(current_user_id, entryId)
        
        if not existing_mood:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mood entry not found"
            )
        
        if existing_mood.get('userId') != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this mood entry"
            )
        
        # Elimina
        success = await firebase_service.delete_mood_entry(current_user_id, entryId)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete mood"
            )
        
        return None  # 204 No Content
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete mood: {str(e)}"
        )
