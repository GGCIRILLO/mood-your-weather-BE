"""
Servizi per interazione con Firebase Realtime Database
"""
from firebase_admin import db, auth as firebase_auth
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from models import MoodEntry, MoodEmoji, Location, ExternalWeather
import uuid


class FirebaseService:
    """Servizio per operazioni Firebase Realtime Database"""
    
    @staticmethod
    def get_user_ref(user_id: str):
        """Ottieni reference al nodo user"""
        ref = db.reference(f'/users/{user_id}')
        return ref
    
    @staticmethod
    def get_moods_ref(user_id: str):
        """Ottieni reference ai mood entries di un utente"""
        return db.reference(f'/moods/{user_id}')
    
    @staticmethod
    def get_stats_ref(user_id: str):
        """Ottieni reference alle statistiche utente"""
        return db.reference(f'/stats/{user_id}')
    
    # ==================== User Operations ====================
    
    @staticmethod
    async def create_user_profile(user_id: str, email: str, name: Optional[str] = None) -> Dict:
        """Crea profilo utente nel database"""
        user_data = {
            'email': email,
            'name': name or email.split('@')[0],
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'settings': {
                'notifications': True,
                'theme': 'auto'
            }
        }
        
        FirebaseService.get_user_ref(user_id).set(user_data)
        return user_data
    
    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict]:
        """Ottieni profilo utente"""
        result = FirebaseService.get_user_ref(user_id).get()
        return result if isinstance(result, dict) else None
    
    @staticmethod
    async def delete_user_data(user_id: str):
        """Elimina tutti i dati utente (GDPR compliance)"""
        # Elimina mood entries
        FirebaseService.get_moods_ref(user_id).delete()
        # Elimina statistiche
        FirebaseService.get_stats_ref(user_id).delete()
        # Elimina profilo
        FirebaseService.get_user_ref(user_id).delete()
    
    # ==================== Mood Operations ====================
    
    @staticmethod
    async def create_mood_entry(mood_data: Dict) -> str:
        """Crea nuovo mood entry"""
        user_id = mood_data['userId']
        entry_id = str(uuid.uuid4())
        
        print("mood data in service:", mood_data)
        
        # Aggiungi metadata
        mood_data['entryId'] = entry_id
        mood_data['createdAt'] = datetime.now(timezone.utc).isoformat()
        mood_data['timestamp'] = mood_data.get('timestamp', datetime.now(timezone.utc)).isoformat()
        
        # Serializza emojis e location
        if 'emojis' in mood_data and isinstance(mood_data['emojis'], list):
            print("Serializing emojis:", mood_data['emojis'])
            mood_data['emojis'] = [str(e) for e in mood_data['emojis']]
        
        if 'location' in mood_data and mood_data['location']:
            loc = mood_data['location']
            # Handle both object (Pydantic) and dict access
            lat = getattr(loc, 'lat', loc.get('lat') if isinstance(loc, dict) else None)
            lon = getattr(loc, 'lon', loc.get('lon') if isinstance(loc, dict) else None)
            
            if lat is not None and lon is not None:
                mood_data['location'] = {
                    'lat': lat,
                    'lon': lon
                }
            else:
                # Ensure we don't persist unexpected or non-serializable location shapes
                mood_data['location'] = None
        
        # Salva nel database
        FirebaseService.get_moods_ref(user_id).child(entry_id).set(mood_data)
        
        # Aggiorna statistiche in background
        await FirebaseService.update_user_stats(user_id)
        
        return entry_id
    
    @staticmethod
    async def get_mood_entry(user_id: str, entry_id: str) -> Optional[Dict]:
        """Ottieni singolo mood entry"""
        result = FirebaseService.get_moods_ref(user_id).child(entry_id).get()
        return result if isinstance(result, dict) else None
    
    @staticmethod
    async def get_mood_entries(
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Dict], int]:
        """
        Ottieni lista mood entries con filtri e paginazione
        Returns: (entries, total_count)
        """
        moods_ref = FirebaseService.get_moods_ref(user_id)
        all_moods_raw = moods_ref.get()
        all_moods: Dict = all_moods_raw if isinstance(all_moods_raw, dict) else {}
        
        # Converti in lista
        moods_list = []
        for entry_id, mood_data in all_moods.items():
            mood_data['entryId'] = entry_id
            moods_list.append(mood_data)
        
        # Filtra per date
        if start_date or end_date:
            filtered = []
            for mood in moods_list:
                timestamp = datetime.fromisoformat(mood['timestamp'].replace('Z', '+00:00'))
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered.append(mood)
            moods_list = filtered
        
        # Ordina per timestamp (più recenti prima)
        moods_list.sort(key=lambda x: x['timestamp'], reverse=True)
        
        total = len(moods_list)
        
        # Paginazione
        paginated = moods_list[offset:offset + limit]
                
        return paginated, total
    
    @staticmethod
    async def update_mood_entry(user_id: str, entry_id: str, update_data: Dict) -> bool:
        """Aggiorna mood entry esistente"""
        mood_ref = FirebaseService.get_moods_ref(user_id).child(entry_id)
        
        # Verifica esistenza
        if not mood_ref.get():
            return False
        
        # Aggiungi timestamp aggiornamento
        update_data['updatedAt'] = datetime.now(timezone.utc).isoformat()
        
        # Serializza emojis se presenti
        if 'emojis' in update_data and update_data['emojis']:
            update_data['emojis'] = [str(e) for e in update_data['emojis']]
        
        mood_ref.update(update_data)
        
        # Aggiorna statistiche
        await FirebaseService.update_user_stats(user_id)
        
        return True
    
    @staticmethod
    async def delete_mood_entry(user_id: str, entry_id: str) -> bool:
        """Elimina mood entry"""
        mood_ref = FirebaseService.get_moods_ref(user_id).child(entry_id)
        
        if not mood_ref.get():
            return False
        
        mood_ref.delete()
        
        # Aggiorna statistiche
        await FirebaseService.update_user_stats(user_id)
        
        return True
    
    # ==================== Statistics Operations ====================
    
    @staticmethod
    async def update_user_stats(user_id: str):
        """Ricalcola e aggiorna statistiche utente"""
        moods_data_raw = FirebaseService.get_moods_ref(user_id).get()
        moods_data: Dict = moods_data_raw if isinstance(moods_data_raw, dict) else {}
        
        if not moods_data:
            return
        
        moods_list = list(moods_data.values())
        total_entries = len(moods_list)
        
        # Calcola streak
        current_streak, longest_streak = FirebaseService._calculate_streaks(moods_list)
        
        # Calcola dominant mood
        emoji_counts = {}
        total_intensity = 0
        
        for mood in moods_list:
            for emoji in mood.get('emojis', []):
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
            total_intensity += mood.get('intensity', 0)
        
        dominant_mood = max(emoji_counts.items(), key=lambda x: x[1])[0] if emoji_counts else None
        average_intensity = total_intensity / total_entries if total_entries > 0 else 0
        
        # Calcola ritmo settimanale
        weekly_rhythm = FirebaseService._calculate_weekly_rhythm(moods_list)
        
        stats = {
            'totalEntries': total_entries,
            'currentStreak': current_streak,
            'longestStreak': longest_streak,
            'dominantMood': dominant_mood,
            'averageIntensity': round(average_intensity, 2),
            'weeklyRhythm': weekly_rhythm,
            'lastUpdated': datetime.utcnow().isoformat()
        }
        
        FirebaseService.get_stats_ref(user_id).set(stats)
    
    @staticmethod
    def _calculate_streaks(moods_list: List[Dict]) -> tuple[int, int]:
        """Calcola current e longest streak"""
        if not moods_list:
            return 0, 0
        
        # Ordina per timestamp
        sorted_moods = sorted(moods_list, key=lambda x: x['timestamp'])
        
        # Estrai date uniche
        dates = set()
        for mood in sorted_moods:
            timestamp = datetime.fromisoformat(mood['timestamp'].replace('Z', '+00:00'))
            dates.add(timestamp.date())
        
        dates = sorted(dates, reverse=True)
        
        if not dates:
            return 0, 0
        
        # Calcola current streak
        current_streak = 0
        today = datetime.utcnow().date()
        
        for i, date in enumerate(dates):
            expected_date = today - timedelta(days=i)
            if date == expected_date:
                current_streak += 1
            else:
                break
        
        # Calcola longest streak
        longest_streak = 1
        temp_streak = 1
        
        for i in range(len(dates) - 1):
            diff = (dates[i] - dates[i + 1]).days
            if diff == 1:
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1
        
        return current_streak, longest_streak
    
    @staticmethod
    def _calculate_weekly_rhythm(moods_list: List[Dict]) -> Dict[str, float]:
        """Calcola media intensità per giorno settimana"""
        weekday_data = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
        
        for mood in moods_list:
            timestamp = datetime.fromisoformat(mood['timestamp'].replace('Z', '+00:00'))
            weekday = timestamp.weekday()
            weekday_data[weekday].append(mood.get('intensity', 0))
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        rhythm = {}
        
        for i, day in enumerate(days):
            intensities = weekday_data[i]
            rhythm[day] = round(sum(intensities) / len(intensities), 2) if intensities else 0
        
        return rhythm
    
    @staticmethod
    async def get_user_stats(user_id: str) -> Optional[Dict]:
        """Ottieni statistiche utente"""
        stats_raw = FirebaseService.get_stats_ref(user_id).get()
        stats = stats_raw if isinstance(stats_raw, dict) else None
        
        # Se non esistono, calcolale
        if not stats:
            await FirebaseService.update_user_stats(user_id)
            stats_raw = FirebaseService.get_stats_ref(user_id).get()
            stats = stats_raw if isinstance(stats_raw, dict) else None
        
        return stats
    
    @staticmethod
    async def get_calendar_data(user_id: str, year: int, month: int) -> Dict[str, Dict]:
        """Ottieni dati calendario per mese specifico"""
        # Calcola range date
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        moods, _ = await FirebaseService.get_mood_entries(
            user_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000  # Max entries per mese
        )
        
        # Organizza per data
        calendar_data = {}
        for mood in moods:
            timestamp = datetime.fromisoformat(mood['timestamp'].replace('Z', '+00:00'))
            date_key = timestamp.strftime('%Y-%m-%d')
            
            if date_key not in calendar_data:
                calendar_data[date_key] = {
                    'emojis': mood.get('emojis', []),
                    'intensity': mood.get('intensity', 0),
                    'hasNote': bool(mood.get('note'))
                }
        
        return calendar_data



    # ==================== Notification Operations ====================
    
    @staticmethod
    async def save_fcm_token(user_id: str, token: str):
        """Salva token FCM per utente"""
        FirebaseService.get_user_ref(user_id).child('fcmToken').set(token)
    
    @staticmethod
    async def get_fcm_token(user_id: str) -> Optional[str]:
        """Ottieni token FCM utente"""
        token = FirebaseService.get_user_ref(user_id).child('fcmToken').get()
        return token if isinstance(token, str) else None

    @staticmethod
    async def send_push_notification(token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
        """Invia notifica push via FCM"""
        from firebase_admin import messaging
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data,
                token=token,
            )
            response = messaging.send(message)
            print("Successfully sent message:", response)
            return True
        except Exception as e:
            print("Error sending message:", e)
            return False

# Istanza singleton
firebase_service = FirebaseService()
