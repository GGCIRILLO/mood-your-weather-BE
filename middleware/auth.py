"""
Middleware e dependencies per autenticazione e rate limiting
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth
from typing import Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import asyncio


# ==================== Security ====================

security = HTTPBearer()


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verifica token Firebase JWT e ritorna decoded token con user info
    Raises HTTPException 401 se token non valido
    """
    try:
        token = credentials.credentials
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token  # Contiene: uid, email, email_verified, etc.
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_current_user_id(user: dict = Depends(verify_firebase_token)) -> str:
    """Estrae user ID dal token verificato"""
    return user['uid']


async def verify_user_ownership(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id)
) -> str:
    """
    Verifica che l'utente corrente sia il proprietario della risorsa
    Usato per proteggere endpoint che richiedono ownership
    """
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
    return user_id


# ==================== Rate Limiting ====================

class RateLimiter:
    """
    Rate limiter semplice in-memory
    Per produzione, usare Redis o simili
    """
    def __init__(self):
        # user_id -> [(timestamp1, timestamp2, ...)]
        self.requests: defaultdict = defaultdict(list)
        self.cleanup_interval = 60  # Secondi tra cleanup
        self.last_cleanup = datetime.now(timezone.utc)

    def _cleanup_old_requests(self):
        """Rimuovi timestamp vecchi per liberare memoria"""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).seconds < self.cleanup_interval:
            return
        
        cutoff = now - timedelta(minutes=2)
        for user_id in list(self.requests.keys()):
            self.requests[user_id] = [
                ts for ts in self.requests[user_id]
                if ts > cutoff
            ]
            # Rimuovi user se nessuna request recente
            if not self.requests[user_id]:
                del self.requests[user_id]
        
        self.last_cleanup = now
    
    async def check_rate_limit(
        self,
        user_id: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> bool:
        """
        Verifica se user ha superato rate limit
        Returns True se OK, False se limite superato
        """
        self._cleanup_old_requests()

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)
        
        # Filtra request nel window
        recent_requests = [
            ts for ts in self.requests[user_id]
            if ts > window_start
        ]
        
        if len(recent_requests) >= max_requests:
            return False
        
        # Aggiungi nuova request
        self.requests[user_id].append(now)
        return True


# Istanza globale rate limiter
rate_limiter = RateLimiter()


async def check_rate_limit(
    request: Request,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Dependency per verificare rate limit
    Solleva HTTPException 429 se limite superato
    """
    if not await rate_limiter.check_rate_limit(current_user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 100 requests per minute."
        )


# ==================== Optional Auth ====================

async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[dict]:
    """
    Autenticazione opzionale - ritorna user info se token presente, None altrimenti
    Utile per endpoint che hanno comportamento diverso per utenti autenticati/non
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token
    except:
        return None
