"""
Router per export dati
"""
import os
import logging
import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse

from models import ExportRequest, ExportResponse
from middleware.auth import get_current_user_id
from services.firebase_service import firebase_service

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])

@router.post("/csv")
async def export_to_csv(
    request: ExportRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Export dati mood in formato CSV (Download diretto)
    """
    if request.userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only export your own data"
        )
    
    try:
        # Fetch all moods
        moods, total = await firebase_service.get_mood_entries(
            user_id=current_user_id,
            limit=10000 
        )
        
        # Prepare CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Date', 'Time', 'Emojis', 'Intensity', 'Note', 'Weather', 'Temperature'])
        
        # Rows
        for mood in moods:
            # Parse timestamp
            if 'timestamp' in mood:
                 ts = mood['timestamp'] # string ISO
                 # Simple split for date/time if simple string manipulation, or parsing
                 # Assuming ISO-8601: 2024-01-27T15:00:00+00:00
                 date_part = ts.split('T')[0]
                 time_part = ts.split('T')[1].split('+')[0].split('.')[0] if 'T' in ts else ""
            else:
                 date_part, time_part = "", ""

            emojis = ", ".join(mood.get('emojis', []))
            
            # Weather info
            weather_main = ""
            temp = ""
            if mood.get('externalWeather'):
                weather_main = mood['externalWeather'].get('weather_main', '')
                temp = str(mood['externalWeather'].get('temp', ''))

            writer.writerow([
                date_part,
                time_part,
                emojis,
                mood.get('intensity', 0),
                mood.get('note', ''),
                weather_main,
                temp
            ])
            
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=moods_export.csv"}
        )

    except Exception as e:
        logger.error(f"CSV Export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Lista formati export supportati
    """
    return {
        "formats": [
            {
                "format": "csv",
                "name": "CSV File",
                "description": "Export as CSV file for download",
                "implemented": True
            }
        ]
    }
