# Mood Your Weather - Backend Copilot Instructions

## Architecture Overview

FastAPI backend for a mood-tracking mobile app with weather correlation. Key components:

- **Firebase Integration**: Authentication via Firebase Admin SDK + Realtime Database for data persistence
- **Router Layer** ([routers/](../routers/)): Domain-based endpoints (auth, moods, stats, weather, sync, nlp, export)
- **Service Layer** ([services/firebase_service.py](../services/firebase_service.py)): Single `FirebaseService` class with static methods for all DB operations
- **Middleware** ([middleware/auth.py](../middleware/auth.py)): Firebase JWT verification + in-memory rate limiting (100 req/min per user)
- **Models** ([models.py](../models.py)): Pydantic models with custom validators (e.g., timezone-aware timestamps, emoji validation)

## Critical Patterns

### Firebase Realtime Database Structure

```
/users/{userId}          # User profiles and settings
/moods/{userId}/{entryId}  # Mood entries (one per day max)
/stats/{userId}          # Computed statistics (streak, dominant mood, etc.)
```

### Authentication Flow

1. Client authenticates via Firebase Client SDK (Google/Apple/Email)
2. Client sends `idToken` in `Authorization: Bearer` header
3. Backend verifies token using `verify_firebase_token()` dependency
4. Extract `userId` with `get_current_user_id()` dependency

**Important**: Always use `current_user_id = Depends(get_current_user_id)` in protected endpoints. Never trust `userId` from request body without verification.

### Mood Entry Business Logic

- **One mood per day**: Creating a mood checks for existing entry on same date and updates it if found (see [routers/moods.py](../routers/moods.py) L35-75)
- **Timezone-aware timestamps**: All timestamps MUST be UTC-aware. Use `datetime.now(timezone.utc)` and the `make_aware` validator in `MoodCreate`
- **Auto-stats update**: Creating/updating moods triggers `update_user_stats()` in background to recompute streak, dominant mood, etc.

### Weather Integration

- OpenWeatherMap API with **10-minute in-memory cache** (see [routers/weather.py](../routers/weather.py))
- Cache key: rounded coordinates to 2 decimals for geographic proximity
- Free tier limits: 60 calls/min, handle 429 rate limits gracefully
- Always use `units=metric` for Celsius

## Development Workflow

### Running the Server

```bash
# Development (auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or with FastAPI CLI
fastapi dev main.py

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Testing

```bash
pytest tests/ -v
```

**Note**: Tests are minimal (see [tests/test_auth.py](../tests/test_auth.py)). Firebase and OpenWeatherMap interactions are not mocked yet. Use manual testing via `/docs` endpoint.

### Environment Setup

Required files:

- `.env` with `OPENWEATHER_API_KEY` and `FIREBASE_DATABASE_URL`
- `mood-your-weather-firebase-adminsdk-*.json` (Firebase service account key) in project root

## Common Pitfalls

1. **Timezone issues**: Always use `timezone.utc`, never naive datetime objects
2. **Rate limiting**: Current implementation is in-memory; resets on server restart. For production, replace with Redis
3. **Firebase initialization**: `firebase_config.py` is imported in [main.py](../main.py) L8 to initialize on startup. Don't re-initialize elsewhere
4. **CORS**: Mobile app origins are hardcoded in [main.py](../main.py) L45-52. Add production domains before deploying
5. **Skeleton endpoints**: `/nlp` and `/export` routers exist but have placeholder implementations

## Adding New Endpoints

1. Create Pydantic models in [models.py](../models.py) with validators
2. Add business logic as static methods in `FirebaseService` class
3. Create router file in `routers/` with authentication dependencies
4. Include router in [main.py](../main.py) L63-69
5. Update root endpoint's `endpoints` dict for discoverability

## Firebase Service Patterns

All database operations use path-based references:

```python
db.reference(f'/users/{user_id}')
db.reference(f'/moods/{user_id}/{entry_id}')
```

Methods follow naming conventions:

- `create_*`: Insert new record, return ID
- `get_*`: Query single or multiple records
- `update_*`: Modify existing record, return success bool
- `delete_*`: Remove record(s)

Always call `await firebase_service.update_user_stats(user_id)` after mood CRUD operations to keep stats consistent.
