"""
Router per analisi NLP (Natural Language Processing)
"""
from fastapi import APIRouter, HTTPException, status, Depends
from models import NLPAnalyzeRequest, NLPAnalyzeResponse, MoodEmoji
from middleware.auth import get_current_user_id
from google.cloud import language_v1
import os
import logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nlp", tags=["NLP"])

@router.post("/analyze", response_model=NLPAnalyzeResponse)
async def analyze_sentiment(
    request: NLPAnalyzeRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Analisi sentiment di note testuali con Google Cloud NLP API
    """
    try:
        # Check if Google Credentials are set
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set. Using mock NLP response.")
             return NLPAnalyzeResponse(
                sentiment="neutral",
                score=0.0,
                magnitude=0.0,
                emojis_suggested=[MoodEmoji.CLOUDY]
            )

        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(
            content=request.text,
            type_=language_v1.Document.Type.PLAIN_TEXT
        )
        
        response = client.analyze_sentiment(request={'document': document})
        sentiment = response.document_sentiment
        
        score = sentiment.score
        magnitude = sentiment.magnitude
        
        # Map sentiment to MoodEmoji
        # Score range: -1.0 (negative) to 1.0 (positive)
        suggested_emojis = []
        sentiment_label = "neutral"
        
        if score > 0.25:
            sentiment_label = "positive"
            suggested_emojis.append(MoodEmoji.SUNNY)
            if magnitude > 0.6:
                 suggested_emojis.append(MoodEmoji.PARTLY) # Excited/Active
        elif score < -0.25:
            sentiment_label = "negative"
            suggested_emojis.append(MoodEmoji.RAINY)
            if magnitude > 0.6:
                suggested_emojis.append(MoodEmoji.STORMY)
        else:
            sentiment_label = "neutral"
            suggested_emojis.append(MoodEmoji.CLOUDY)
            if magnitude > 0.5:
                suggested_emojis.append(MoodEmoji.PARTLY)

        # Fallback if empty (shouldn't happen with logic above)
        if not suggested_emojis:
             suggested_emojis.append(MoodEmoji.CLOUDY)

        return NLPAnalyzeResponse(
            sentiment=sentiment_label,
            score=score,
            magnitude=magnitude,
            emojis_suggested=suggested_emojis
        )

    except Exception as e:
        logger.error(f"NLP Analysis failed: {str(e)}")
        # Graceful degradation
        return NLPAnalyzeResponse(
            sentiment="error",
            score=0.0,
            magnitude=0.0,
            emojis_suggested=[MoodEmoji.CLOUDY] # Default fallback
        )


@router.get("/health")
async def nlp_health_check():
    """
    Health check per servizio NLP
    """
    creds_set = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    return {
        "service": "NLP",
        "status": "active" if creds_set else "mocked",
        "message": "Google Cloud NLP integration active" if creds_set else "Credentials missing, running in mock mode"
    }
