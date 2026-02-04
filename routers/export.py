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
from google.oauth2 import service_account
from googleapiclient.discovery import build

from models import ExportRequest, ExportResponse
from middleware.auth import get_current_user_id
from services.firebase_service import firebase_service

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])

@router.post("/csv")
async def export_to_csv(
    request: ExportRequest,
  current_user_id: str = "test_user_verifying" # Depends(get_current_user_id)
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


@router.post("/google-sheets", response_model=ExportResponse)
async def export_to_google_sheets(
    request: ExportRequest,
  current_user_id: str = "test_user_verifying" # Depends(get_current_user_id)
):
    """
    Export dati mood su Google Sheets
    """
    if request.userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only export your own data"
        )
    
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             return ExportResponse(
                success=False,
                message="Google Service Account credentials missing"
             )

        # 1. Fetch data
        moods, total = await firebase_service.get_mood_entries(
            user_id=current_user_id,
            limit=10000 
        )
        
        # 2. Setup Google Sheets Service
        creds = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']
        )
        service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # 3. Create Spreadsheet
        spreadsheet_body = {
            'properties': {
                'title': f'Mood Tracker Export - {datetime.utcnow().strftime("%Y-%m-%d")}'
            }
        }
        
        sheet = service.spreadsheets().create(
            body=spreadsheet_body,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()
        
        spreadsheet_id = sheet.get('spreadsheetId')
        spreadsheet_url = sheet.get('spreadsheetUrl')
        
        # 4. Prepare Data
        # Header
        values = [['Date', 'Time', 'Emojis', 'Intensity', 'Note', 'Weather', 'Temperature']]
        
        for mood in moods:
            ts = mood.get('timestamp', '')
            if 'T' in ts:
                 date_part = ts.split('T')[0]
                 time_part = ts.split('T')[1].split('+')[0].split('.')[0]
            else:
                 date_part, time_part = ts, ""
            
            emojis = ", ".join(mood.get('emojis', []))
            
            weather_main = ""
            temp = ""
            if mood.get('externalWeather'):
                weather_main = mood['externalWeather'].get('weather_main', '')
                temp = mood['externalWeather'].get('temp', '')

            values.append([
                date_part,
                time_part,
                emojis,
                mood.get('intensity', 0),
                mood.get('note', ''),
                weather_main,
                temp
            ])
            
        # 5. Write Data
        body = {
            'values': values
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        # 6. Share with User (if email available)
        # For now, we make it accessible to anyone with link OR share with specific email if we had it easily accessible here
        # Ideally we fetch user email from Firebase Auth profile.
        # Let's try to fetch user profile to get email
        user_profile = await firebase_service.get_user_profile(current_user_id)
        user_email = user_profile.get('email') if user_profile else None
        
        if user_email:
            # Grant permission to user
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body={
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': user_email
                },
                fields='id'
            ).execute()
        else:
             # Fallback: Make it reader to anyone with link (less secure but works for demo)
             # Or just return URL and hope Service Account owns it? User won't be able to open it unless shared.
             # Let's warn in message if not shared.
             pass

        return ExportResponse(
            success=True,
            url=spreadsheet_url,
            message=f"Export successful! Shared with {user_email}" if user_email else "Export created but could not access user email to share. Please contact support."
        )

    except Exception as e:
        logger.error(f"Google Sheets Export failed: {str(e)}")
        # Check for specific errors like 403 Forbidden etc
        return ExportResponse(
             success=False,
             message=f"Export failed: {str(e)}"
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
            },
            {
                "format": "google_sheets",
                "name": "Google Sheets",
                "description": "Export to Google Sheets",
                "implemented": False
            }
        ]
    }
