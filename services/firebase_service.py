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
        
        now_utc = datetime.now(timezone.utc)
        
        # Aggiungi metadata
        mood_data['entryId'] = entry_id
        mood_data['createdAt'] = now_utc.isoformat()
        mood_data['updatedAt'] = now_utc.isoformat()
        
        # Se timestamp non è già un datetime object, usa now_utc
        if 'timestamp' not in mood_data or not isinstance(mood_data['timestamp'], datetime):
            mood_data['timestamp'] = now_utc.isoformat()
        else:
            mood_data['timestamp'] = mood_data['timestamp'].isoformat()
        
        # Serializza emojis e location
        if 'emojis' in mood_data and isinstance(mood_data['emojis'], list):
            mood_data['emojis'] = [str(e) for e in mood_data['emojis']]
        
        if 'location' in mood_data and mood_data['location']:
            mood_data['location'] = {
                'lat': mood_data['location'].lat,
                'lon': mood_data['location'].lon
            }
        
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
            # Anche se non ci sono mood, potremmo avere altre statistiche da preservare
            existing_stats = await FirebaseService.get_user_stats(user_id) or {}
            unlocked_badges = existing_stats.get('unlockedBadges', [])
            
            # Check mindful_moment badge even if no moods
            if existing_stats.get('mindfulMomentsCount', 0) >= 1 and "mindful_moment" not in unlocked_badges:
                unlocked_badges.append("mindful_moment")

            stats = {
                'totalEntries': 0,
                'currentStreak': 0,
                'longestStreak': 0,
                'dominantMood': None,
                'averageIntensity': 0,
                'weeklyRhythm': {d: 0 for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']},
                'mindfulMomentsCount': existing_stats.get('mindfulMomentsCount', 0),
                'unlockedBadges': unlocked_badges,
                'lastUpdated': datetime.now(timezone.utc).isoformat()
            }
            FirebaseService.get_stats_ref(user_id).set(stats)
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
        
        # Recupera statistiche esistenti per preservare campi non calcolati qui
        stats_ref = FirebaseService.get_stats_ref(user_id)
        existing_stats_raw = stats_ref.get()
        existing_stats = existing_stats_raw if isinstance(existing_stats_raw, dict) else {}
        unlocked_badges = existing_stats.get('unlockedBadges', [])
        
        # Verifica sblocco badge basato sui mood correnti
        if current_streak >= 7 and "7_day_streak" not in unlocked_badges:
            unlocked_badges.append("7_day_streak")
            
        has_note = any(mood.get('note') and str(mood.get('note')).strip() for mood in moods_list)
        if has_note and "storyteller" not in unlocked_badges:
            unlocked_badges.append("storyteller")
            
        has_mixed_weather = any(len(mood.get('emojis', [])) >= 2 for mood in moods_list)
        if has_mixed_weather and "weather_mixologist" not in unlocked_badges:
            unlocked_badges.append("weather_mixologist")
            
        if existing_stats.get('mindfulMomentsCount', 0) >= 1 and "mindful_moment" not in unlocked_badges:
            unlocked_badges.append("mindful_moment")

        stats = {
            'totalEntries': total_entries,
            'currentStreak': current_streak,
            'longestStreak': longest_streak,
            'dominantMood': dominant_mood,
            'averageIntensity': round(average_intensity, 2),
            'weeklyRhythm': weekly_rhythm,
            'mindfulMomentsCount': existing_stats.get('mindfulMomentsCount', 0),
            'unlockedBadges': unlocked_badges,
            'lastUpdated': datetime.now(timezone.utc).isoformat()
        }
        stats_ref.set(stats)
    
    @staticmethod
    def _calculate_streaks(moods_list: List[Dict]) -> tuple[int, int]:
        """
        Calcola current e longest streak.
        Uno streak è 'corrente' se l'ultimo log è oggi o ieri.
        """
        if not moods_list:
            return 0, 0
        
        # Estrai date uniche (timezone aware)
        dates = set()
        for mood in moods_list:
            ts_str = mood.get('timestamp')
            if not ts_str:
                continue
            if 'Z' in ts_str:
                ts_str = ts_str.replace('Z', '+00:00')
            try:
                timestamp = datetime.fromisoformat(ts_str)
                dates.add(timestamp.date())
            except ValueError:
                continue
        
        sorted_dates = sorted(list(dates), reverse=True)

        if not sorted_dates:
            return 0, 0

        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        
        # Current streak logic: must have logged today or yesterday
        current_streak = 0
        if sorted_dates[0] >= yesterday:
            anchor_date = sorted_dates[0]
            for i, date in enumerate(sorted_dates):
                if date == anchor_date - timedelta(days=i):
                    current_streak += 1
                else:
                    break
        else:
            # Last log was before yesterday, streak is broken
            current_streak = 0
            
        # Longest streak logic
        longest_streak = 1
        temp_streak = 1
        for i in range(len(sorted_dates) - 1):
            if (sorted_dates[i] - sorted_dates[i + 1]).days == 1:
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
        stats_ref = FirebaseService.get_stats_ref(user_id)
        stats_raw = stats_ref.get()
        stats = stats_raw if isinstance(stats_raw, dict) else None
        
        if stats:
            # Verifica se lo streak è potenzialmente scaduto (se l'ultimo update non è di oggi)
            last_updated_str = stats.get('lastUpdated')
            if last_updated_str:
                last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                if last_updated.date() < datetime.now(timezone.utc).date():
                    # Giorno cambiato: ricalcola per aggiornare lo streak
                    await FirebaseService.update_user_stats(user_id)
                    stats = stats_ref.get()
        else:
            # Se non esistono, calcolale
            await FirebaseService.update_user_stats(user_id)
            stats = stats_ref.get()
        
        return stats if isinstance(stats, dict) else None
    
    @staticmethod
    async def get_calendar_data(user_id: str, year: int, month: int) -> Dict[str, Dict]:
        """Ottieni dati calendario per mese specifico"""
        # Calcola range date
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        
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

    @staticmethod
    async def increment_mindful_moments(user_id: str):
        """Incrementa il contatore delle sessioni di mindfulness"""
        stats_ref = FirebaseService.get_stats_ref(user_id)
        stats = stats_ref.get()
        
        if not isinstance(stats, dict):
            # Se le statistiche non esistono, inizializzale
            await FirebaseService.update_user_stats(user_id)
            stats = stats_ref.get()
            
        current_count = stats.get('mindfulMomentsCount', 0) if isinstance(stats, dict) else 0
        new_count = current_count + 1
        
        updates = {'mindfulMomentsCount': new_count}
        
        # Verifica sblocco badge
        unlocked_badges = stats.get('unlockedBadges', []) if isinstance(stats, dict) else []
        if new_count >= 1 and "mindful_moment" not in unlocked_badges:
            unlocked_badges.append("mindful_moment")
            updates['unlockedBadges'] = unlocked_badges
            
        stats_ref.update(updates)


# Istanza singleton
firebase_service = FirebaseService()
