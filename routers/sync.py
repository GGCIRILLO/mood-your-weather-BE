"""
Router per sincronizzazione offline
"""
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from typing import List
from models import SyncRequest, SyncResponse, SyncResult, MoodCreate
from services.firebase_service import firebase_service
from middleware.auth import get_current_user_id, check_rate_limit


router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("", response_model=SyncResponse)
async def sync_mood_entries(
    sync_data: SyncRequest,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Sincronizzazione batch per supporto offline
    
    - Accetta array di mood entries dal client
    - Risolve conflitti basandosi su timestamp (latest wins)
    - Ritorna mapping tra localId e serverId
    - Max 100 entries per request
    
    Conflict resolution:
    - Se entry con stesso timestamp esiste, aggiorna
    - Altrimenti crea nuovo entry
    """
    results: List[SyncResult] = []
    success_count = 0
    error_count = 0
    
    for entry in sync_data.entries:
        try:
            # Verifica ownership
            if entry.userId != current_user_id:
                results.append(SyncResult(
                    localId=entry.localId,
                    status="error",
                    message="User ID mismatch"
                ))
                error_count += 1
                continue
            
            # Controlla se esiste già un entry con stesso timestamp
            existing_moods, total_count = await firebase_service.get_mood_entries(
                user_id=current_user_id,
                start_date=entry.timestamp,
                end_date=entry.timestamp,
                limit=1
            )
            
            server_id = None
            sync_status = "created"
            
            if existing_moods:
                # Conflict: usa timestamp più recente
                existing = existing_moods[0]
                existing_client_ts = existing.get('clientTimestamp')
                
                if existing_client_ts:
                    existing_dt = datetime.fromisoformat(existing_client_ts.replace('Z', '+00:00'))
                    if entry.clientTimestamp > existing_dt:
                        # Entry client è più recente, aggiorna
                        server_id = existing['entryId']
                        update_data = {
                            'emojis': [str(e) for e in entry.emojis],
                            'intensity': entry.intensity,
                            'note': entry.note,
                            'clientTimestamp': entry.clientTimestamp.isoformat()
                        }
                        
                        if entry.location:
                            update_data['location'] = {
                                'lat': entry.location.lat,
                                'lon': entry.location.lon
                            }
                        
                        await firebase_service.update_mood_entry(
                            current_user_id,
                            server_id,
                            update_data
                        )
                        sync_status = "updated"
                    else:
                        # Server è più recente, skip
                        server_id = existing['entryId']
                        sync_status = "conflict"
                else:
                    # Esiste ma senza clientTimestamp, aggiorna
                    server_id = existing['entryId']
                    sync_status = "updated"
            
            if not server_id:
                # Crea nuovo entry
                mood_data = {
                    'userId': entry.userId,
                    'timestamp': entry.timestamp,
                    'emojis': entry.emojis,
                    'intensity': entry.intensity,
                    'note': entry.note,
                    'location': entry.location,
                    'clientTimestamp': entry.clientTimestamp.isoformat()
                }
                
                server_id = await firebase_service.create_mood_entry(mood_data)
            
            results.append(SyncResult(
                localId=entry.localId,
                serverId=server_id,
                status=sync_status,
                serverTimestamp=datetime.utcnow()
            ))
            success_count += 1
        
        except Exception as e:
            results.append(SyncResult(
                localId=entry.localId,
                status="error",
                message=str(e)
            ))
            error_count += 1
    
    return SyncResponse(
        results=results,
        totalProcessed=len(sync_data.entries),
        successCount=success_count,
        errorCount=error_count
    )


@router.get("/status/{userId}")
async def get_sync_status(
    userId: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Ottieni stato sincronizzazione per utente
    
    Ritorna info su ultimo sync e statistiche
    """
    if userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own sync status"
        )
    
    try:
        # Ottieni statistiche
        stats = await firebase_service.get_user_stats(userId)
        
        # In produzione, tracciare ultimo sync in database
        return {
            "userId": userId,
            "lastSync": None,  # TODO: implementare tracking
            "totalEntries": stats.get('totalEntries', 0) if stats else 0,
            "needsSync": False  # TODO: logica più sofisticata
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )
