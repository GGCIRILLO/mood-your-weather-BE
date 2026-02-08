"""
Router per analisi NLP (Natural Language Processing)
"""
from fastapi import APIRouter, HTTPException, status, Depends
from models import NLPAnalyzeRequest, NLPAnalyzeResponse, MoodEmoji
from middleware.auth import get_current_user_id
import httpx
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
    Analisi sentiment di note testuali con Hugging Face Inference API
    Model: cardiffnlp/twitter-roberta-base-sentiment-latest
    """
    try:
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token or hf_token == "hf_":
             logger.warning("HF_TOKEN not set. Using mock NLP response.")
             return NLPAnalyzeResponse(
                sentiment="neutral",
                score=0.0,
                magnitude=0.0,
                emojis_suggested=[MoodEmoji.CLOUDY]
            )

        # Updated API Domain
        api_url = "https://router.huggingface.co/hf-inference/models/cardiffnlp/twitter-roberta-base-sentiment-latest"
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {"inputs": request.text}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload)
            
        if response.status_code != 200:
            logger.error(f"HF API Error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail=f"NLP Provider Error: {response.status_code}"
            )
        
        # Hugging Face returns a list of list of dicts
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            scores = result[0]
        elif isinstance(result, dict) and 'error' in result:
             logger.error(f"HF Model Loading: {result}")
             raise HTTPException(status_code=503, detail="Model is loading, please try again")
        else:
             scores = result 
             
        # Sort by score descending to find dominant sentiment
        scores.sort(key=lambda x: x['score'], reverse=True)
        top_sentiment = scores[0]
        
        raw_label = top_sentiment['label'] 
        score = top_sentiment['score']
        
        # Normalize labels for cardiffnlp/twitter-roberta-base-sentiment-latest
        # Mapping: negative, neutral, positive
        label = raw_label.lower()
        

        suggested_emojis = []

        if label == "positive":
            suggested_emojis.append(MoodEmoji.SUNNY)
            if score > 0.8:
                suggested_emojis.append(MoodEmoji.PARTLY)
        elif label == "negative":
            suggested_emojis.append(MoodEmoji.RAINY)
            if score > 0.8:
                suggested_emojis.append(MoodEmoji.STORMY)
        else: # neutral
            suggested_emojis.append(MoodEmoji.CLOUDY)
            if score > 0.6:
                suggested_emojis.append(MoodEmoji.PARTLY)

        return NLPAnalyzeResponse(
            sentiment=label,
            score=round(score, 2), # Using probability as score
            magnitude=round(score, 2), # Using probability as magnitude proxy
            emojis_suggested=suggested_emojis
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NLP Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"NLP Analysis failed: {str(e)}"
        )


@router.get("/health")
async def nlp_health_check():
    """
    Health check per servizio NLP
    """
    creds_set = bool(os.getenv("HF_TOKEN"))
    return {
        "service": "NLP",
        "provider": "Hugging Face API",
        "status": "active" if creds_set else "mocked",
        "message": "HF integration active" if creds_set else "Token missing, running in mock mode"
    }
