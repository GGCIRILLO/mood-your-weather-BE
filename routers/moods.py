"""
Router per CRUD mood entries
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime, timezone
from models import (
    MoodCreate, MoodUpdate, MoodEntry, MoodList,
    Location, ExternalWeather, MoodEntryWithNLP, MoodListWithNLP
)
from services.firebase_service import firebase_service
from services.geocoding import reverse_geocode, format_location_short
from middleware.auth import get_current_user_id, check_rate_limit
from routers.weather import fetch_and_parse_weather, fetch_openweather_data
from routers.nlp import analyze_mood_entry



router = APIRouter(prefix="/moods", tags=["Moods"])


async def fetch_weather_for_location(location: Location) -> Optional[ExternalWeather]:
    """
    Recupera dati meteo per una location e li converte in ExternalWeather

    Returns None se il fetch fallisce (non solleva eccezioni)
    """
    try:
        weather_data = await fetch_openweather_data(location.lat, location.lon)

        return ExternalWeather(
            temp=weather_data['main']['temp'],
            feels_like=weather_data['main']['feels_like'],
            humidity=weather_data['main']['humidity'],
            weather_main=weather_data['weather'][0]['main'],
            weather_description=weather_data['weather'][0]['description'],
            icon=weather_data['weather'][0]['icon']
        )
    except Exception:
        # Se il fetch meteo fallisce, non blocchiamo l'operazione
        # Il mood verrà salvato senza dati meteo
        return None


@router.post("", response_model=MoodEntry, status_code=status.HTTP_201_CREATED)
async def create_mood(
    mood_data: MoodCreate,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Crea o aggiorna mood entry per la giornata corrente
    
    - Se esiste già un mood per la giornata, lo aggiorna
    - Altrimenti crea un nuovo mood entry
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
        # Genera timestamp server-side in UTC
        now_utc = datetime.now(timezone.utc)
        mood_date = now_utc.date()
        
        # Cerca mood esistente per la stessa giornata UTC
        start_of_day = datetime.combine(mood_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = datetime.combine(mood_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        existing_moods, total = await firebase_service.get_mood_entries(
            user_id=current_user_id,
            start_date=start_of_day,
            end_date=end_of_day,
            limit=1,
            offset=0
        )
        
        
        mood_dict = mood_data.model_dump()
        
        # 3. Fetch external weather and geocode if location is provided
        if mood_data.location:
             # Fetch weather data
             external_weather = await fetch_and_parse_weather(
                 mood_data.location.lat, 
                 mood_data.location.lon
             )
             if external_weather:
                 mood_dict['externalWeather'] = external_weather.model_dump()
             
             # Reverse geocoding for human-readable name
             geocoded = await reverse_geocode(mood_data.location.lat, mood_data.location.lon)
             if geocoded:
                 mood_dict['location']['name'] = format_location_short(geocoded)
        
        
        if existing_moods:
            # Aggiorna il mood esistente
            existing_entry = existing_moods[0]
            entry_id = existing_entry['entryId']

            # Prepara dati per update (escludi userId, mantieni timestamp originale)
            update_dict = {
                'emojis': mood_dict['emojis'],
                'intensity': mood_dict['intensity'],
                'note': mood_dict.get('note'),
                'location': mood_dict.get('location'),
                'externalWeather': mood_dict.get('externalWeather')
            }
            
            if 'externalWeather' in mood_dict:
                update_dict['externalWeather'] = mood_dict['externalWeather']
            
            success = await firebase_service.update_mood_entry(
                current_user_id,
                entry_id,
                update_dict
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update existing mood"
                )
        else:
            # Crea nuovo entry
            entry_id = await firebase_service.create_mood_entry(mood_dict)
        
        # Recupera entry completo
        final_mood = await firebase_service.get_mood_entry(current_user_id, entry_id)
        
        if not final_mood:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve mood entry"
            )
        
        return MoodEntry(**final_mood)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update mood: {str(e)}"
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


@router.get("/journal", response_model=MoodListWithNLP)
async def get_moods_with_notes(
    userId: Optional[str] = Query(None, description="Filter by user ID"),
    startDate: Optional[datetime] = Query(None, description="Start date filter (ISO-8601)"),
    endDate: Optional[datetime] = Query(None, description="End date filter (ISO-8601)"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Lista mood entries che hanno una nota allegata, con analisi NLP

    - Filtra solo moods con nota non vuota
    - Per ogni mood, esegue analisi NLP considerando:
      * La nota dell'utente
      * Gli emojis e l'intensità del mood
      * Le condizioni meteo (se disponibili)
    - Restituisce mood entries completi + risultati analisi NLP
    - Supporta filtri per data range e paginazione
    - Richiede autenticazione
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
        # Recupera tutti i mood entries (con limite più alto per poter filtrare)
        # Nota: idealmente il filtro dovrebbe essere fatto a livello DB
        moods_data, total_all = await firebase_service.get_mood_entries(
            user_id=target_user_id,
            start_date=startDate,
            end_date=endDate,
            limit=1000,  # Limite alto per recuperare tutti i mood nel range
            offset=0
        )

        # Filtra solo mood con note non vuote
        moods_with_notes = [
            mood for mood in moods_data
            if mood.get('note') and mood.get('note').strip()
        ]

        total_with_notes = len(moods_with_notes)

        # Applica paginazione manualmente
        paginated_moods = moods_with_notes[offset:offset + limit]

        # Converti in MoodEntry objects ed esegui analisi NLP per ognuno
        mood_entries_with_nlp = []

        for mood_data in paginated_moods:
            mood_entry = MoodEntry(**mood_data)

            # Esegui analisi NLP considerando mood, nota e meteo
            nlp_analysis = await analyze_mood_entry(mood_entry)

            # Crea oggetto combinato
            mood_with_nlp = MoodEntryWithNLP(
                mood=mood_entry,
                nlpAnalysis=nlp_analysis
            )
            mood_entries_with_nlp.append(mood_with_nlp)
            
        print(mood_entries_with_nlp)

        return MoodListWithNLP(
            items=mood_entries_with_nlp,
            total=total_with_notes,
            limit=limit,
            offset=offset,
            hasMore=(offset + limit) < total_with_notes
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch moods with notes: {str(e)}"
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

        # Recupera dati meteo e geocoding se location è presente nell'update
        if 'location' in update_dict:
            loc_data = Location(**update_dict['location'])
            
            # Fetch weather
            weather_data = await fetch_weather_for_location(loc_data)
            if weather_data:
                update_dict['externalWeather'] = weather_data.model_dump()
            
            # Reverse geocoding for human-readable name
            geocoded = await reverse_geocode(loc_data.lat, loc_data.lon)
            if geocoded:
                update_dict['location']['name'] = format_location_short(geocoded)

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
        
