"""
Router per autenticazione utenti
"""
from fastapi import APIRouter, HTTPException, status, Depends
from firebase_admin import auth as firebase_auth
from models import UserRegister, UserLogin, SocialLogin, AuthResponse
from services.firebase_service import firebase_service
from middleware.auth import get_current_user_id, check_rate_limit


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister):
    """
    Registrazione nuovo utente con email/password
    
    - Crea utente in Firebase Authentication
    - Crea profilo utente nel database
    - Ritorna userId e custom token
    """
    try:
        # Crea utente in Firebase Auth
        user_record = firebase_auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.name
        )
        
        # Crea profilo nel database
        await firebase_service.create_user_profile(
            user_id=user_record.uid,
            email=user_data.email,
            name=user_data.name
        )
        
        # Genera custom token (il client lo userà per ottenere ID token)
        custom_token = firebase_auth.create_custom_token(user_record.uid)
        
        return AuthResponse(
            userId=user_record.uid,
            token=custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token,
            email=user_data.email,
            name=user_data.name
        )
    
    except firebase_auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(credentials: UserLogin):
    """
    Login con email/password
    
    Nota: Firebase Admin SDK non supporta login diretto con password.
    In produzione, il client dovrebbe usare Firebase Client SDK per login
    e passare l'ID token al backend.
    
    Questo endpoint è un placeholder che verifica l'esistenza dell'utente
    e genera un custom token.
    """
    try:
        # Ottieni utente per email
        user = firebase_auth.get_user_by_email(credentials.email)
        
        # In produzione, il client usa Firebase Client SDK per autenticarsi
        # Qui generiamo un custom token per testing
        custom_token = firebase_auth.create_custom_token(user.uid)
        
        # Ottieni profilo
        profile = await firebase_service.get_user_profile(user.uid)
        
        return AuthResponse(
            userId=user.uid,
            token=custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token,
            email=user.email,
            name=profile.get('name') if profile else None
        )
    
    except firebase_auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/social-login", response_model=AuthResponse)
async def social_login(social_data: SocialLogin):
    """
    Login con Google/Apple
    
    Riceve ID token da provider sociale (generato dal client)
    e lo verifica con Firebase
    """
    try:
        # Verifica token del provider
        decoded_token = firebase_auth.verify_id_token(social_data.idToken)
        user_id = decoded_token['uid']
        
        # Ottieni info utente
        user = firebase_auth.get_user(user_id)
        
        # Crea profilo se non esiste
        profile = await firebase_service.get_user_profile(user_id)
        if not profile:
            await firebase_service.create_user_profile(
                user_id=user_id,
                email=user.email or "",
                name=user.display_name
            )
            profile = await firebase_service.get_user_profile(user_id)
        
        # Genera nuovo custom token
        custom_token = firebase_auth.create_custom_token(user_id)
        
        return AuthResponse(
            userId=user_id,
            token=custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token,
            email=user.email,
            name=profile.get('name') if profile else None
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Social login failed: {str(e)}"
        )


@router.delete("/user/{userId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    userId: str,
    current_user_id: str = Depends(get_current_user_id),
    _: None = Depends(check_rate_limit)
):
    """
    Cancellazione account e dati utente (GDPR compliance)
    
    - Elimina utente da Firebase Authentication
    - Elimina tutti i dati utente dal database (moods, stats, profile)
    - Richiede autenticazione
    """
    # Verifica ownership
    if userId != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account"
        )
    
    try:
        # Elimina tutti i dati dal database
        await firebase_service.delete_user_data(userId)
        
        # Elimina utente da Firebase Auth
        firebase_auth.delete_user(userId)
        
        return None  # 204 No Content
    
    except firebase_auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account deletion failed: {str(e)}"
        )


@router.get("/verify", response_model=dict)
async def verify_token(current_user_id: str = Depends(get_current_user_id)):
    """
    Verifica validità token e ritorna info utente
    Utile per client per verificare se sessione è ancora valida
    """
    try:
        user = firebase_auth.get_user(current_user_id)
        profile = await firebase_service.get_user_profile(current_user_id)
        
        return {
            "userId": user.uid,
            "email": user.email,
            "name": profile.get('name') if profile else None,
            "emailVerified": user.email_verified
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )
