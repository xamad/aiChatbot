from typing import List, Dict
from ..base import IntentProviderBase
from plugins_func.functions.play_music import initialize_music_handler
from config.logger import setup_logging
import re
import json
import hashlib
import time

TAG = __name__
logger = setup_logging()


class IntentProvider(IntentProviderBase):
    def __init__(self, config):
        super().__init__(config)
        self.llm = None
        self.promot = ""
        # 导入全局缓存管理器
        from core.utils.cache.manager import cache_manager, CacheType

        self.cache_manager = cache_manager
        self.CacheType = CacheType
        self.history_count = 4  # 默认使用最近4条对话记录

    def get_intent_system_prompt(self, functions_list: str) -> str:
        """
        Generate system prompt for intent detection - optimized for Llama/Groq
        """
        # Build compact function list
        functions_desc = "AVAILABLE FUNCTIONS:\n"
        for func in functions_list:
            func_info = func.get("function", {})
            name = func_info.get("name", "")
            desc = func_info.get("description", "")
            params = func_info.get("parameters", {})

            functions_desc += f"- {name}: {desc}"
            if params and params.get("properties"):
                param_names = list(params.get("properties", {}).keys())
                if param_names:
                    functions_desc += f" (params: {', '.join(param_names)})"
            functions_desc += "\n"

        prompt = f"""You are a JSON-only intent classifier. Output ONLY valid JSON, no text.

{functions_desc}

RULES:
1. Match user intent to a function from the list above
2. For time/date queries: {{"function_call": {{"name": "result_for_context"}}}}
3. For greetings/chat: {{"function_call": {{"name": "continue_chat"}}}}
4. For function match: {{"function_call": {{"name": "function_name", "arguments": {{...}}}}}}

EXAMPLES:
User: "che ore sono?" -> {{"function_call": {{"name": "result_for_context"}}}}
User: "ciao come stai?" -> {{"function_call": {{"name": "continue_chat"}}}}
User: "che tempo fa a Roma?" -> {{"function_call": {{"name": "meteo_italia", "arguments": {{"city": "Roma"}}}}}}
User: "accendi la radio" -> {{"function_call": {{"name": "radio_italia", "arguments": {{"action": "play"}}}}}}
User: "sintonizzati su radio zeta" -> {{"function_call": {{"name": "radio_italia", "arguments": {{"action": "play", "station": "radio zeta"}}}}}}
User: "metti radio deejay" -> {{"function_call": {{"name": "radio_italia", "arguments": {{"action": "play", "station": "radio deejay"}}}}}}
User: "quali radio hai" -> {{"function_call": {{"name": "radio_italia", "arguments": {{"action": "list"}}}}}}
User: "raccontami una barzelletta" -> {{"function_call": {{"name": "barzelletta_bambini"}}}}
User: "Giannino" -> {{"function_call": {{"name": "giannino_easter_egg", "arguments": {{"domanda": "Giannino"}}}}}}
User: "tu chi sei?" -> {{"function_call": {{"name": "chi_sono"}}}}
User: "come ti chiami?" -> {{"function_call": {{"name": "chi_sono"}}}}
User: "cosa sai fare?" -> {{"function_call": {{"name": "chi_sono"}}}}
User: "cosa posso cucinare con pasta e uova?" -> {{"function_call": {{"name": "ricette_ingredienti", "arguments": {{"ingredienti": "pasta, uova"}}}}}}
User: "ho in casa pollo e patate, cosa preparo?" -> {{"function_call": {{"name": "ricette_ingredienti", "arguments": {{"ingredienti": "pollo, patate"}}}}}}
User: "canta paraponziponzipò" -> {{"function_call": {{"name": "osterie_goliardiche"}}}}
User: "all'osteria numero cinque" -> {{"function_call": {{"name": "osterie_goliardiche", "arguments": {{"numero": 5}}}}}}
User: "fai il verso del gallo" -> {{"function_call": {{"name": "versi_animali", "arguments": {{"animale": "gallo"}}}}}}
User: "imita un animale da cortile" -> {{"function_call": {{"name": "versi_animali"}}}}
User: "trasformati in pirata" -> {{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "pirata"}}}}}}
User: "parla come un robot" -> {{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "robot"}}}}}}
User: "fai il nonno burbero" -> {{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "nonno"}}}}}}
User: "torna normale" -> {{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "normale"}}}}}}
User: "mi sento solo" -> {{"function_call": {{"name": "compagno_antisolitudine"}}}}
User: "fammi compagnia" -> {{"function_call": {{"name": "compagno_antisolitudine"}}}}
User: "insultami" -> {{"function_call": {{"name": "easter_egg_folli", "arguments": {{"tipo": "insulto"}}}}}}
User: "confessami, ho peccato" -> {{"function_call": {{"name": "easter_egg_folli", "arguments": {{"tipo": "confessione"}}}}}}
User: "litiga con te stesso" -> {{"function_call": {{"name": "easter_egg_folli", "arguments": {{"tipo": "litigio"}}}}}}
User: "suono della pioggia" -> {{"function_call": {{"name": "suoni_ambiente", "arguments": {{"suono": "pioggia"}}}}}}
User: "rumore bianco per dormire" -> {{"function_call": {{"name": "suoni_ambiente", "arguments": {{"suono": "rumore_bianco"}}}}}}
User: "onde del mare" -> {{"function_call": {{"name": "suoni_ambiente", "arguments": {{"suono": "onde"}}}}}}
User: "aggiungi latte alla spesa" -> {{"function_call": {{"name": "shopping_vocale", "arguments": {{"azione": "aggiungi", "prodotto": "latte"}}}}}}
User: "cosa devo comprare" -> {{"function_call": {{"name": "shopping_vocale", "arguments": {{"azione": "leggi"}}}}}}
User: "traduci ciao in inglese" -> {{"function_call": {{"name": "traduttore_realtime", "arguments": {{"testo": "ciao", "lingua_destinazione": "inglese"}}}}}}
User: "come si dice grazie in francese" -> {{"function_call": {{"name": "traduttore_realtime", "arguments": {{"testo": "grazie", "lingua_destinazione": "francese"}}}}}}
User: "fai un beatbox" -> {{"function_call": {{"name": "beatbox_umano"}}}}
User: "fammi una base trap" -> {{"function_call": {{"name": "beatbox_umano", "arguments": {{"stile": "trap"}}}}}}
User: "beat hip hop" -> {{"function_call": {{"name": "beatbox_umano", "arguments": {{"stile": "hip hop"}}}}}}
User: "cuciniamo la carbonara" -> {{"function_call": {{"name": "cooking_companion", "arguments": {{"ricetta": "carbonara"}}}}}}
User: "prossimo step" -> {{"function_call": {{"name": "cooking_companion", "arguments": {{"azione": "avanti"}}}}}}
User: "avanti con la ricetta" -> {{"function_call": {{"name": "cooking_companion", "arguments": {{"azione": "avanti"}}}}}}
User: "ripeti lo step" -> {{"function_call": {{"name": "cooking_companion", "arguments": {{"azione": "ripeti"}}}}}}
User: "ricordami che le chiavi sono nel cassetto" -> {{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "ricorda", "contenuto": "le chiavi sono nel cassetto"}}}}}}
User: "dove ho messo le chiavi" -> {{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "cerca", "contenuto": "chiavi"}}}}}}
User: "ricorda che Marco è allergico alle noci" -> {{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "ricorda", "contenuto": "Marco è allergico alle noci"}}}}}}
User: "cosa sai di Marco" -> {{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "cerca", "contenuto": "Marco"}}}}}}
User: "cerca su google intelligenza artificiale" -> {{"function_call": {{"name": "web_search", "arguments": {{"query": "intelligenza artificiale"}}}}}}
User: "cercami informazioni sulla Luna" -> {{"function_call": {{"name": "web_search", "arguments": {{"query": "Luna"}}}}}}
User: "trova su internet notizie bitcoin" -> {{"function_call": {{"name": "web_search", "arguments": {{"query": "notizie bitcoin"}}}}}}
User: "cos'è il machine learning" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "cos'è il machine learning"}}}}}}
User: "cosa significa algoritmo" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "cosa significa algoritmo"}}}}}}
User: "chi è Elon Musk" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "chi è Elon Musk"}}}}}}
User: "spiegami la fotosintesi" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "spiegami la fotosintesi"}}}}}}
User: "come funziona un motore" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "come funziona un motore"}}}}}}
User: "perché il cielo è blu" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "perché il cielo è blu"}}}}}}
User: "chiedi a gpt cosa sono i buchi neri" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "cosa sono i buchi neri"}}}}}}
User: "cerca con gemini la teoria della relatività" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "la teoria della relatività"}}}}}}
User: "domanda ai: come si forma un arcobaleno" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "come si forma un arcobaleno"}}}}}}
User: "chiedi a claude perché i gatti fanno le fusa" -> {{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "perché i gatti fanno le fusa"}}}}}}
User: "cerca immagini di natura" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "cerca", "query": "natura"}}}}}}
User: "cerca immagini di gatti" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "cerca", "query": "gatti"}}}}}}
User: "mostrami foto di montagne" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "cerca", "query": "montagne"}}}}}}
User: "fammi vedere immagini di tramonti" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "cerca", "query": "tramonti"}}}}}}
User: "prossima immagine" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "prossima"}}}}}}
User: "ferma slideshow" -> {{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "ferma"}}}}}}
User: "cerca gif di cani" -> {{"function_call": {{"name": "cerca_gif", "arguments": {{"azione": "cerca", "query": "cani"}}}}}}
User: "mostra gif divertenti" -> {{"function_call": {{"name": "cerca_gif", "arguments": {{"azione": "cerca", "query": "divertenti"}}}}}}
User: "gif trending" -> {{"function_call": {{"name": "cerca_gif", "arguments": {{"azione": "trending"}}}}}}
User: "cosa è successo oggi nella storia" -> {{"function_call": {{"name": "accadde_oggi"}}}}
User: "accadde oggi" -> {{"function_call": {{"name": "accadde_oggi"}}}}
User: "metti un timer di 5 minuti" -> {{"function_call": {{"name": "timer_sveglia", "arguments": {{"minuti": 5}}}}}}
User: "svegliami tra 10 minuti" -> {{"function_call": {{"name": "timer_sveglia", "arguments": {{"minuti": 10}}}}}}
User: "imposta sveglia alle 7" -> {{"function_call": {{"name": "timer_sveglia", "arguments": {{"ora": "07:00"}}}}}}
User: "notizie di oggi" -> {{"function_call": {{"name": "notizie_italia"}}}}
User: "ultime notizie" -> {{"function_call": {{"name": "notizie_italia"}}}}
User: "quali sono le news" -> {{"function_call": {{"name": "notizie_italia"}}}}
User: "oroscopo ariete" -> {{"function_call": {{"name": "oroscopo", "arguments": {{"segno": "ariete"}}}}}}
User: "che dice l'oroscopo" -> {{"function_call": {{"name": "oroscopo"}}}}
User: "estrazioni del lotto" -> {{"function_call": {{"name": "lotto_estrazioni"}}}}
User: "numeri del lotto" -> {{"function_call": {{"name": "lotto_estrazioni"}}}}
User: "santo del giorno" -> {{"function_call": {{"name": "santo_del_giorno"}}}}
User: "che santo è oggi" -> {{"function_call": {{"name": "santo_del_giorno"}}}}
User: "ricetta della pasta al pesto" -> {{"function_call": {{"name": "ricette", "arguments": {{"ricetta": "pasta al pesto"}}}}}}
User: "come si fa la pizza" -> {{"function_call": {{"name": "ricette", "arguments": {{"ricetta": "pizza"}}}}}}
User: "dimmi una curiosità" -> {{"function_call": {{"name": "curiosita"}}}}
User: "lo sapevi che" -> {{"function_call": {{"name": "curiosita"}}}}
User: "proverbio del giorno" -> {{"function_call": {{"name": "proverbi_italiani"}}}}
User: "dimmi un proverbio" -> {{"function_call": {{"name": "proverbi_italiani"}}}}
User: "frase del giorno" -> {{"function_call": {{"name": "frase_del_giorno"}}}}
User: "citazione motivazionale" -> {{"function_call": {{"name": "frase_del_giorno"}}}}
User: "facciamo un quiz" -> {{"function_call": {{"name": "quiz_trivia"}}}}
User: "quiz di cultura generale" -> {{"function_call": {{"name": "quiz_trivia"}}}}
User: "raccontami una storia" -> {{"function_call": {{"name": "storie_bambini"}}}}
User: "storia della buonanotte" -> {{"function_call": {{"name": "storie_bambini"}}}}
User: "giochiamo all'impiccato" -> {{"function_call": {{"name": "impiccato"}}}}
User: "gioco dell'impiccato" -> {{"function_call": {{"name": "impiccato"}}}}
User: "giochiamo a battaglia navale" -> {{"function_call": {{"name": "battaglia_navale"}}}}
User: "tira un dado" -> {{"function_call": {{"name": "dado"}}}}
User: "lancia i dadi" -> {{"function_call": {{"name": "dado"}}}}
User: "20 domande" -> {{"function_call": {{"name": "venti_domande"}}}}
User: "indovina cosa penso" -> {{"function_call": {{"name": "venti_domande"}}}}
User: "chi vuol essere milionario" -> {{"function_call": {{"name": "chi_vuol_essere"}}}}
User: "facciamo meditazione" -> {{"function_call": {{"name": "meditazione"}}}}
User: "guidami in una meditazione" -> {{"function_call": {{"name": "meditazione"}}}}
User: "ginnastica dolce" -> {{"function_call": {{"name": "ginnastica_dolce"}}}}
User: "esercizi di stretching" -> {{"function_call": {{"name": "ginnastica_dolce"}}}}
User: "podcast italiano" -> {{"function_call": {{"name": "podcast_italia"}}}}
User: "metti un podcast" -> {{"function_call": {{"name": "podcast_italia"}}}}
User: "karaoke" -> {{"function_call": {{"name": "karaoke"}}}}
User: "cantiamo insieme" -> {{"function_call": {{"name": "karaoke"}}}}
User: "calcola 5 per 8" -> {{"function_call": {{"name": "calcolatrice", "arguments": {{"espressione": "5*8"}}}}}}
User: "quanto fa 100 diviso 4" -> {{"function_call": {{"name": "calcolatrice", "arguments": {{"espressione": "100/4"}}}}}}
User: "converti 10 euro in dollari" -> {{"function_call": {{"name": "convertitore", "arguments": {{"valore": 10, "da": "euro", "a": "dollari"}}}}}}
User: "quanti km sono 5 miglia" -> {{"function_call": {{"name": "convertitore", "arguments": {{"valore": 5, "da": "miglia", "a": "km"}}}}}}
User: "promemoria alle 15 chiamare Mario" -> {{"function_call": {{"name": "promemoria", "arguments": {{"ora": "15:00", "messaggio": "chiamare Mario"}}}}}}
User: "ricordami di comprare il pane" -> {{"function_call": {{"name": "promemoria", "arguments": {{"messaggio": "comprare il pane"}}}}}}
User: "prendi nota che devo pagare bolletta" -> {{"function_call": {{"name": "note_vocali", "arguments": {{"nota": "pagare bolletta"}}}}}}
User: "scrivi appunto riunione domani" -> {{"function_call": {{"name": "note_vocali", "arguments": {{"nota": "riunione domani"}}}}}}
User: "quali funzioni hai" -> {{"function_call": {{"name": "sommario_funzioni"}}}}
User: "help" -> {{"function_call": {{"name": "sommario_funzioni"}}}}
User: "lista funzioni" -> {{"function_call": {{"name": "sommario_funzioni"}}}}
User: "cosa sai fare" -> {{"function_call": {{"name": "sommario_funzioni"}}}}
User: "come ti uso" -> {{"function_call": {{"name": "sommario_funzioni"}}}}
User: "come si attiva la radio" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "radio"}}}}}}
User: "come uso il timer" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "timer"}}}}}}
User: "come attivo il meteo" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "meteo"}}}}}}
User: "come faccio a usare le immagini" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "immagini"}}}}}}
User: "come funziona il quiz" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "quiz"}}}}}}
User: "funzioni audio" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"categoria": "audio"}}}}}}
User: "funzioni giochi" -> {{"function_call": {{"name": "sommario_funzioni", "arguments": {{"categoria": "giochi"}}}}}}
User: "emergenza" -> {{"function_call": {{"name": "sos_emergenza"}}}}
User: "chiama aiuto" -> {{"function_call": {{"name": "sos_emergenza"}}}}
User: "numero dei carabinieri" -> {{"function_call": {{"name": "numeri_utili", "arguments": {{"servizio": "carabinieri"}}}}}}
User: "numero della polizia" -> {{"function_call": {{"name": "numeri_utili", "arguments": {{"servizio": "polizia"}}}}}}
User: "ristoranti vicino a me" -> {{"function_call": {{"name": "guida_ristoranti"}}}}
User: "consiglia un ristorante" -> {{"function_call": {{"name": "guida_ristoranti"}}}}
User: "cosa vedere a Firenze" -> {{"function_call": {{"name": "guida_turistica", "arguments": {{"citta": "Firenze"}}}}}}
User: "guida turistica Roma" -> {{"function_call": {{"name": "guida_turistica", "arguments": {{"citta": "Roma"}}}}}}
User: "accendi la luce" -> {{"function_call": {{"name": "domotica", "arguments": {{"comando": "accendi", "dispositivo": "luce"}}}}}}
User: "spegni il condizionatore" -> {{"function_call": {{"name": "domotica", "arguments": {{"comando": "spegni", "dispositivo": "condizionatore"}}}}}}
User: "come mi sento oggi" -> {{"function_call": {{"name": "check_benessere"}}}}
User: "controllo benessere" -> {{"function_call": {{"name": "check_benessere"}}}}
User: "non riesco a dormire" -> {{"function_call": {{"name": "compagno_notturno"}}}}
User: "ho bisogno di sfogarmi" -> {{"function_call": {{"name": "supporto_emotivo"}}}}
User: "mi sento triste" -> {{"function_call": {{"name": "supporto_emotivo"}}}}
User: "fammi un complimento" -> {{"function_call": {{"name": "complimenti"}}}}
User: "briefing mattutino" -> {{"function_call": {{"name": "briefing_mattutino"}}}}
User: "buongiorno cosa c'è oggi" -> {{"function_call": {{"name": "briefing_mattutino"}}}}
User: "leggi questa pagina web" -> {{"function_call": {{"name": "leggi_pagina"}}}}
User: "oracolo dimmi il futuro" -> {{"function_call": {{"name": "oracolo"}}}}
User: "consulta l'oracolo" -> {{"function_call": {{"name": "oracolo"}}}}
User: "genera una rima con amore" -> {{"function_call": {{"name": "genera_rime", "arguments": {{"parola": "amore"}}}}}}
User: "trova una rima per sole" -> {{"function_call": {{"name": "genera_rime", "arguments": {{"parola": "sole"}}}}}}

OUTPUT FORMAT: Return ONLY the JSON object. No markdown, no explanation, no text before or after."""
        return prompt

    def replyResult(self, text: str, original_text: str):
        llm_result = self.llm.response_no_stream(
            system_prompt=text,
            user_prompt="请根据以上内容，像人类一样说话的口吻回复用户，要求简洁，请直接返回结果。用户现在说："
            + original_text,
        )
        return llm_result

    async def detect_intent(self, conn, dialogue_history: List[Dict], text: str) -> str:
        if not self.llm:
            raise ValueError("LLM provider not set")
        if conn.func_handler is None:
            return '{"function_call": {"name": "continue_chat"}}'

        # Pre-check per pattern comuni (bypass LLM per richieste ovvie)
        text_lower = text.lower().strip()

        # Funzione helper per match
        def match_any(keywords):
            return any(kw in text_lower for kw in keywords)

        # ============ STOP GLOBALE - FERMA QUALSIASI FUNZIONE ============
        # Solo per comandi brevi e diretti (max 3 parole o frasi specifiche)
        stop_keywords = ['stop', 'basta', 'fermati', 'smetti', 'esci', 'abbandona', 'annulla',
                         'interrompi', 'torna indietro', 'fine']
        stop_phrases = ['ferma tutto', 'stop tutto', 'cancella tutto', 'basta così',
                        'ferma la radio', 'stop radio', 'ferma slideshow', 'ferma immagini',
                        'spegni radio', 'spegni tutto']

        # Check frasi specifiche
        if any(phrase in text_lower for phrase in stop_phrases):
            return '{"function_call": {"name": "handle_exit_intent"}}'

        # Check comandi brevi (max 3 parole)
        words = text_lower.split()
        if len(words) <= 3 and any(kw in text_lower for kw in stop_keywords):
            return '{"function_call": {"name": "handle_exit_intent"}}'

        # ============ GESTIONE PROFILI SKILL ============
        # NOTA: "modalità interprete" va a TRADUTTORE, "attiva modalità [profilo]" va qui
        # Escludiamo esplicitamente "interprete" dal match "attiva modalità" per evitare conflitti
        is_profile_request = match_any(['cambia profilo', 'attiva profilo', 'modalità assistente',
                      'che profilo', 'quale profilo', 'quali profili', 'profili disponibili',
                      'lista profili', 'elenca profili', 'elenco profili'])
        # "attiva modalità X" solo se X non è "interprete" (quello va a traduttore)
        if 'attiva modalità' in text_lower and 'interprete' not in text_lower:
            is_profile_request = True

        if is_profile_request:
            # Estrai nome profilo se presente
            profili = ['generale', 'anziani', 'bambini', 'intrattenimento', 'produttivita', 'produttività',
                       'cultura', 'benessere', 'smart_home', 'domotica', 'interprete', 'cucina', 'notte']
            profilo_trovato = ""
            for p in profili:
                if p in text_lower:
                    profilo_trovato = p
                    break

            if match_any(['che profilo', 'quale profilo', 'profilo attivo', 'sono in che']):
                return '{"function_call": {"name": "cambia_profilo", "arguments": {"azione": "stato"}}}'
            elif match_any(['quali profili', 'profili disponibili', 'elenco profili', 'lista profili', 'elenca profili']):
                return '{"function_call": {"name": "cambia_profilo", "arguments": {"azione": "lista"}}}'
            elif profilo_trovato:
                return f'{{"function_call": {{"name": "cambia_profilo", "arguments": {{"azione": "cambia", "profilo": "{profilo_trovato}"}}}}}}'
            else:
                return '{"function_call": {"name": "cambia_profilo", "arguments": {"azione": "lista"}}}'

        # ============ RADIO ============
        # Match diretto per nomi radio specifici (senza bisogno della parola "radio")
        radio_names = ['deejay', 'zeta', 'capital', 'm2o', 'radio italia', 'rai radio', '105', 'virgin', 'kiss kiss', 'rtl', 'radicale', 'cusano', 'bbc']
        # Normalizza: "radiozeta" -> "radio zeta", "radioitalia" -> "radio italia"
        text_normalized = re.sub(r'radio(\w)', r'radio \1', text_lower)

        is_radio_request = match_any(['sintonizza', 'sintonizzati', 'metti radio', 'ascolta radio', 'accendi radio',
                                      'fammi sentire', 'fammi ascoltare', 'fai partire'])
        if not is_radio_request:
            # Check se menziona una radio specifica
            for rname in radio_names:
                if rname in text_normalized:
                    is_radio_request = True
                    break

        if is_radio_request:
            # Estrai nome stazione - prova vari pattern
            station = ""
            # Pattern 1: "radio xyz"
            station_match = re.search(r'radio\s*([\w\s\.]+?)(?:\s*$|\s*(?:per|che|cosa))', text_normalized)
            if station_match:
                station = station_match.group(0).strip()
            else:
                # Pattern 2: "sintonizza/sintonizzati su xyz" o "metti xyz" o "fammi sentire xyz"
                station_match = re.search(r'(?:sintonizza|sintonizzati|metti|ascolta|accendi|sentire|ascoltare)\s+(?:su\s+|la\s+)?([\w\s\.]+?)(?:\s*$|\s*(?:per|che|cosa))', text_normalized)
                if station_match:
                    station = station_match.group(1).strip()
                    # Rimuovi "radio" se rimasto
                    station = re.sub(r'^la\s+', '', station)

            if match_any(['elenco', 'lista', 'quali radio']):
                return '{"function_call": {"name": "radio_italia", "arguments": {"action": "list"}}}'
            elif match_any(['stop', 'ferma', 'spegni']):
                return '{"function_call": {"name": "radio_italia", "arguments": {"action": "stop"}}}'
            result = f'{{"function_call": {{"name": "radio_italia", "arguments": {{"action": "play", "station": "{station}"}}}}}}'
            logger.bind(tag=TAG).debug(f"Pre-check: radio -> {result}")
            return result

        # ============ METEO ============
        if match_any(['che tempo fa', 'meteo', 'previsioni', 'piove', 'temperatura', 'come sarà il tempo',
                      'che tempo', 'tempo domani', 'tempo oggi', 'pioverà', 'farà caldo', 'farà freddo']):
            # Estrai città - supporta nomi con più parole
            city_match = re.search(r'(?:a|di|per|su|in)\s+([a-zàèéìòùç\s]+?)(?:\s+(?:domani|oggi|prossimi|nei)|\?|$)', text_lower)
            city = city_match.group(1).strip() if city_match else ""
            result = f'{{"function_call": {{"name": "meteo_italia", "arguments": {{"city": "{city}"}}}}}}'
            logger.bind(tag=TAG).debug(f"Pre-check: meteo -> {result}")
            return result

        # ============ NOTIZIE ============
        if match_any(['notizie', 'ultime notizie', 'news', 'ultime news', 'cosa succede', 'telegiornale',
                      'rassegna stampa', 'dimmi le notizie', 'fammi sentire le notizie', 'leggi le notizie',
                      'giornale', 'cosa è successo', 'novità']):
            return '{"function_call": {"name": "notizie_italia", "arguments": {"action": "headlines"}}}'

        # ============ SMART FRIDGE ============
        if match_any(['frigo', 'frigorifero', 'nel frigo', 'in frigo', 'lista della spesa', 'lista spesa',
                      'cosa devo comprare', 'cosa manca', 'prodotti in scadenza', 'cosa scade',
                      'svuota lista', 'cancella lista', 'togli dalla lista', 'rimuovi dalla lista']):
            # Svuota lista della spesa
            if match_any(['svuota', 'cancella tutto', 'elimina tutto', 'pulisci lista']):
                return '{"function_call": {"name": "smart_fridge", "arguments": {"azione": "svuota_spesa"}}}'
            # Rimuovi dalla lista della spesa
            if match_any(['togli', 'rimuovi', 'cancella', 'elimina']) and match_any(['lista', 'spesa']):
                # Estrai nome prodotto
                prodotto_match = re.search(r'(?:togli|rimuovi|cancella|elimina)\s+(.+?)(?:\s+(?:dalla|nella)\s+lista|\s*$)', text_lower)
                prodotto = prodotto_match.group(1).strip() if prodotto_match else ""
                return f'{{"function_call": {{"name": "smart_fridge", "arguments": {{"azione": "rimuovi_spesa", "prodotto": "{prodotto}"}}}}}}'
            # Aggiungi alla lista della spesa
            if match_any(['aggiungi', 'metti', 'inserisci', 'compra']):
                # Estrai nome prodotto
                prodotto_match = re.search(r'(?:aggiungi|metti|inserisci|compra)\s+(.+?)(?:\s+(?:alla|nella)\s+lista|\s*$)', text_lower)
                prodotto = prodotto_match.group(1).strip() if prodotto_match else ""
                qty_match = re.search(r'(\d+)\s+(?:di\s+)?', text_lower)
                qty = qty_match.group(1) if qty_match else "1"
                return f'{{"function_call": {{"name": "smart_fridge", "arguments": {{"azione": "aggiungi_spesa", "prodotto": "{prodotto}", "quantita": {qty}}}}}}}'
            # Cosa scade / prodotti in scadenza
            if match_any(['scade', 'scadenza', 'scadenze', 'sta per scadere']):
                return '{"function_call": {"name": "smart_fridge", "arguments": {"azione": "scadenze"}}}'
            # Lista della spesa
            if match_any(['lista', 'spesa', 'comprare', 'manca']):
                return '{"function_call": {"name": "smart_fridge", "arguments": {"azione": "spesa"}}}'
            # Inventario / cosa c'è nel frigo
            if match_any(['cosa c', 'inventario', 'contenuto', 'dentro']):
                return '{"function_call": {"name": "smart_fridge", "arguments": {"azione": "inventario"}}}'
            # Default: statistiche
            return '{"function_call": {"name": "smart_fridge", "arguments": {"azione": "statistiche"}}}'

        # ============ CERCA IMMAGINI ============
        if match_any(['cerca immagini', 'cerca foto', 'mostrami immagini', 'mostrami foto',
                      'fammi vedere immagini', 'fammi vedere foto', 'slideshow', 'slideshow di',
                      'immagini di', 'foto di']):
            # Estrai query dall'input
            query_match = re.search(r'(?:di|su|per|con)\s+(.+)', text_lower)
            if query_match:
                query = query_match.group(1).strip()
                return f'{{"function_call": {{"name": "cerca_immagini", "arguments": {{"azione": "cerca", "query": "{query}"}}}}}}'
            return '{"function_call": {"name": "cerca_immagini", "arguments": {"azione": "cerca"}}}'

        # Navigazione slideshow
        if match_any(['prossima immagine', 'immagine successiva', 'avanti immagine', 'next image']):
            return '{"function_call": {"name": "cerca_immagini", "arguments": {"azione": "prossima"}}}'
        if match_any(['immagine precedente', 'indietro immagine', 'torna indietro']):
            return '{"function_call": {"name": "cerca_immagini", "arguments": {"azione": "precedente"}}}'

        # ============ CERCA GIF ============
        if match_any(['cerca gif', 'mostrami gif', 'fammi vedere gif', 'gif di', 'gif animate']):
            query_match = re.search(r'(?:di|su|per|con)\s+(.+)', text_lower)
            if query_match:
                query = query_match.group(1).strip()
                return f'{{"function_call": {{"name": "cerca_gif", "arguments": {{"azione": "cerca", "query": "{query}"}}}}}}'
            return '{"function_call": {"name": "cerca_gif", "arguments": {"azione": "cerca"}}}'

        if match_any(['gif trending', 'gif popolari', 'gif del momento']):
            return '{"function_call": {"name": "cerca_gif", "arguments": {"azione": "trending"}}}'

        # ============ CERCA MUSICA WEB ============
        if match_any(['cerca musica', 'cerca canzone', 'trova musica', 'trova canzone',
                      'metti musica', 'fammi sentire musica', 'scarica musica', 'download musica']):
            query_match = re.search(r'(?:di|su|per|con|intitolata|chiamata)\s+(.+)', text_lower)
            if query_match:
                query = query_match.group(1).strip()
                return f'{{"function_call": {{"name": "cerca_musica_web", "arguments": {{"query": "{query}"}}}}}}'
            return '{"function_call": {"name": "cerca_musica_web"}}'

        # ============ BARZELLETTE ============
        # NON matchare "raccontami una storia" (va a storie_bambini)
        if match_any(['barzelletta', 'battuta', 'fammi ridere', 'raccontami una barzelletta']):
            if match_any(['adulti', 'spinta', 'sconce', 'per grandi']):
                return '{"function_call": {"name": "barzelletta_adulti"}}'
            return '{"function_call": {"name": "barzelletta_bambini"}}'

        # ============ TIMER/SVEGLIA ============
        if match_any(['timer', 'sveglia', 'svegliami', 'countdown']):
            minutes_match = re.search(r'(\d+)\s*minut', text_lower)
            minutes = minutes_match.group(1) if minutes_match else "5"
            if match_any(['cancella', 'stop', 'ferma']):
                return '{"function_call": {"name": "timer_sveglia", "arguments": {"action": "cancel"}}}'
            return f'{{"function_call": {{"name": "timer_sveglia", "arguments": {{"action": "set", "minutes": {minutes}}}}}}}'

        # ============ MEMORIA PERSONALE (prima di promemoria!) ============
        # "ricordami che X" = memoria, "ricordami di fare X" = promemoria
        if match_any(['ricordami che', 'ricorda che', 'ricordati che', 'dove ho messo', 'dove sono le',
                      'dove sta il', 'dove sta la', 'cosa mi hai detto', 'ti avevo detto']):
            if match_any(['dove ho messo', 'dove sono', 'dove sta']):
                return f'{{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "cerca", "contenuto": "{text}"}}}}}}'
            return f'{{"function_call": {{"name": "memoria_personale", "arguments": {{"azione": "ricorda", "contenuto": "{text}"}}}}}}'

        # ============ PROMEMORIA (dopo memoria personale) ============
        # "ricordami di fare X" = promemoria (azione futura)
        if match_any(['ricordami di', 'ricordami tra', 'promemoria', 'non dimenticare di']):
            return f'{{"function_call": {{"name": "promemoria", "arguments": {{"action": "add", "text": "{text}"}}}}}}'

        # ============ CALCOLATRICE ============
        if match_any(['quanto fa', 'calcola', 'somma', 'moltiplica', 'dividi', 'percentuale']):
            return f'{{"function_call": {{"name": "calcolatrice", "arguments": {{"expression": "{text}"}}}}}}'

        # ============ OROSCOPO ============
        # Solo se dice esplicitamente "oroscopo" - NON solo segno zodiacale (evita conflitto giochi)
        if match_any(['oroscopo', 'segno zodiacale', 'che segno', 'dimmi oroscopo', 'oroscopo di oggi']):
            segni = ['ariete', 'toro', 'gemelli', 'cancro', 'leone', 'vergine', 'bilancia', 'scorpione', 'sagittario', 'capricorno', 'acquario', 'pesci']
            segno = next((s for s in segni if s in text_lower), "")
            return f'{{"function_call": {{"name": "oroscopo", "arguments": {{"segno": "{segno}"}}}}}}'

        # ============ OSTERIE GOLIARDICHE ============
        # Controlla se c'è un numero dopo "osteria" - indica filastrocca goliardica
        osteria_num_match = re.search(r'osteria\s*(?:numero\s*)?(\d+)', text_lower)
        if osteria_num_match:
            num = osteria_num_match.group(1)
            return f'{{"function_call": {{"name": "osterie_goliardiche", "arguments": {{"numero": {num}}}}}}}'
        # Altri pattern goliardici
        if match_any(['paraponzi', 'canta osteria', 'canzone goliardica', 'canto goliardico', 'all\'osteria numero', 'filastrocca osteria']):
            num_match = re.search(r'(\d+)', text_lower)
            if num_match:
                return f'{{"function_call": {{"name": "osterie_goliardiche", "arguments": {{"numero": {num_match.group(1)}}}}}}}'
            return '{"function_call": {"name": "osterie_goliardiche"}}'

        # ============ GIANNINI (Easter Egg EPICO!) ============
        # IMPORTANTE: Solo domande brevi o dirette, NON risposte lunghe che contengono il nome
        has_giannino = 'giannini' in text_lower or 'giannino' in text_lower
        if has_giannino:
            # Solo se: testo corto (<60 char) O domanda esplicita
            is_question = match_any(['chi è', 'chi e', 'conosci', 'parlami di', 'dimmi di', 'sai chi è'])
            is_short = len(text.strip()) < 60
            if is_short or is_question:
                return f'{{"function_call": {{"name": "giannino_easter_egg", "arguments": {{"domanda": "{text}"}}}}}}'

        # ============ RICETTE CON INGREDIENTI (prima di ricette generiche!) ============
        if match_any(['cosa posso cucinare', 'ricette con', 'ho in casa', 'cosa preparo con', 'che piatto faccio con', 'idee ricette']):
            ing_match = re.search(r'(?:con|ho)\s+(.+?)(?:\?|$)', text_lower)
            ingredienti = ing_match.group(1) if ing_match else text
            return f'{{"function_call": {{"name": "ricette_ingredienti", "arguments": {{"ingredienti": "{ingredienti}"}}}}}}'

        # ============ RICETTE (generiche) ============
        if match_any(['ricetta', 'come si fa', 'come si cucina', 'prepara']):
            return f'{{"function_call": {{"name": "ricette", "arguments": {{"query": "{text}"}}}}}}'

        # ============ QUIZ/TRIVIA ============
        if match_any(['quiz', 'trivia', 'domanda cultura', 'indovina', 'gioco domande']):
            return '{"function_call": {"name": "quiz_trivia", "arguments": {"action": "start"}}}'

        # ============ STORIE BAMBINI ============
        if match_any(['racconta storia', 'favola', 'fiaba', 'storia della buonanotte', 'raccontami una storia']):
            return '{"function_call": {"name": "storie_bambini"}}'

        # ============ PROVERBI ============
        if match_any(['proverbio', 'detto popolare', 'saggezza popolare', 'modi di dire']):
            return '{"function_call": {"name": "proverbi_italiani"}}'

        # ============ SANTO DEL GIORNO ============
        if match_any(['santo del giorno', 'che santo è', 'san ', 'santa ', 'onomastico']):
            return '{"function_call": {"name": "santo_del_giorno"}}'

        # ============ CURIOSITÀ ============
        # NON matchare "dimmi qualcosa di cattivo" (va a easter_egg)
        if match_any(['curiosità', 'lo sapevi', 'fatto interessante', 'dimmi qualcosa di interessante']):
            return '{"function_call": {"name": "curiosita"}}'

        # ============ FRASE DEL GIORNO ============
        if match_any(['frase del giorno', 'citazione', 'frase motivazionale', 'ispirami']):
            return '{"function_call": {"name": "frase_del_giorno"}}'

        # ============ TRADUTTORE REALTIME ============
        # Pattern specifici per evitare conflitti
        lingue_trad = ['inglese', 'francese', 'spagnolo', 'tedesco', 'portoghese', 'russo', 'cinese', 'giapponese', 'arabo', 'greco', 'olandese', 'polacco', 'coreano', 'turco', 'hindi']

        # MODALITÀ INTERPRETE CONTINUA: "avvia traduttore in X", "traduttore in X", "modalità interprete X"
        # Controlla se è "traduttore in [lingua]" (modalità continua) vs "traduci X in Y" (singola)
        is_interpreter_mode = match_any(['avvia traduttore', 'attiva traduttore', 'modalità interprete', 'fai da interprete', 'aiutami a comunicare'])
        # "traduttore in [lingua]" senza testo da tradurre = modalità continua
        for lingua in lingue_trad:
            if f"traduttore in {lingua}" in text_lower or f"traduttore {lingua}" in text_lower:
                is_interpreter_mode = True
                break
        if is_interpreter_mode:
            lingua_dest = "inglese"
            for lingua in lingue_trad:
                if lingua in text_lower:
                    lingua_dest = lingua
                    break
            return f'{{"function_call": {{"name": "traduttore_realtime", "arguments": {{"testo": "{text}", "lingua_destinazione": "{lingua_dest}", "modalita": "continua"}}}}}}'

        # Match esplicito: "traduci X in Y" o "come si dice X in Y"
        if match_any(['traduci ', 'traduzione ', 'tradurre ', 'traduttore']):
            # Estrai lingua destinazione
            lingua_dest = "inglese"
            for lingua in lingue_trad:
                if f"in {lingua}" in text_lower:
                    lingua_dest = lingua
                    break
            # Estrai testo da tradurre
            testo_match = re.search(r'(?:traduci|traduzione|tradurre)\s+["\']?(.+?)["\']?\s+in\s+\w+', text_lower)
            if not testo_match:
                testo_match = re.search(r'(?:traduci|traduzione|tradurre)\s+(.+?)$', text_lower)
            testo = testo_match.group(1).strip() if testo_match else text
            return f'{{"function_call": {{"name": "traduttore_realtime", "arguments": {{"testo": "{testo}", "lingua_destinazione": "{lingua_dest}"}}}}}}'

        # Match "come si dice X in [lingua]" - solo se c'è la lingua specificata!
        for lingua in lingue_trad:
            if f"in {lingua}" in text_lower and match_any(['come si dice', 'come dico']):
                testo_match = re.search(r'(?:come si dice|come dico)\s+["\']?(.+?)["\']?\s+in\s+\w+', text_lower)
                testo = testo_match.group(1).strip() if testo_match else ""
                return f'{{"function_call": {{"name": "traduttore_realtime", "arguments": {{"testo": "{testo}", "lingua_destinazione": "{lingua}"}}}}}}'

        # ============ SHOPPING VOCALE (Lista Spesa Avanzata) ============
        if match_any(['lista spesa', 'lista della spesa', 'cosa devo comprare', 'cosa manca', 'devo comprare']):
            return '{"function_call": {"name": "shopping_vocale", "arguments": {"azione": "leggi"}}}'
        if match_any(['aggiungi alla spesa', 'metti in lista', 'metti nella spesa']):
            # Estrai prodotto
            prod_match = re.search(r'(?:aggiungi|metti)\s+(.+?)(?:\s+alla|\s+in|$)', text_lower)
            prodotto = prod_match.group(1) if prod_match else ""
            return f'{{"function_call": {{"name": "shopping_vocale", "arguments": {{"azione": "aggiungi", "prodotto": "{prodotto}"}}}}}}'
        if match_any(['ho comprato', 'togli dalla spesa', 'elimina dalla spesa']):
            prod_match = re.search(r'(?:comprato|togli|elimina)\s+(.+?)(?:\s+dalla|$)', text_lower)
            prodotto = prod_match.group(1) if prod_match else ""
            return f'{{"function_call": {{"name": "shopping_vocale", "arguments": {{"azione": "rimuovi", "prodotto": "{prodotto}"}}}}}}'
        if match_any(['svuota la spesa', 'cancella la lista']):
            return '{"function_call": {"name": "shopping_vocale", "arguments": {"azione": "svuota"}}}'

        # ============ DOMOTICA ============
        if match_any(['accendi luce', 'spegni luce', 'accendi presa', 'spegni presa', 'domotica']):
            action = "on" if match_any(['accendi']) else "off" if match_any(['spegni']) else "list"
            device_match = re.search(r'(?:luce|presa|dispositivo)\s+(\w+)', text_lower)
            device = device_match.group(0) if device_match else ""
            return f'{{"function_call": {{"name": "domotica", "arguments": {{"action": "{action}", "device": "{device}"}}}}}}'

        # ============ MESHTASTIC / LORA MESH ============
        # Invia messaggio alla rete mesh LoRa
        if match_any(['messaggio mesh', 'manda lora', 'trasmetti mesh', 'invia mesh',
                      'scrivi mesh', 'dì sulla mesh', 'messaggio radio', 'manda messaggio lora',
                      'walkie talkie', 'trasmetti lora', 'scrivi sulla rete']):
            # Estrai messaggio dal testo
            msg_match = re.search(r'(?:mesh|lora|radio|rete)\s*[:\s]+(.+?)$', text_lower)
            if not msg_match:
                msg_match = re.search(r'(?:manda|invia|trasmetti|scrivi|dì)\s+(?:messaggio\s+)?(?:mesh|lora|radio)?\s*[:\s]*(.+?)$', text_lower)
            messaggio = msg_match.group(1).strip() if msg_match else ""
            return f'{{"function_call": {{"name": "invia_messaggio_mesh", "arguments": {{"messaggio": "{messaggio}"}}}}}}'

        # Leggi messaggi mesh
        if match_any(['leggi mesh', 'messaggi mesh', 'messaggi lora', 'cosa hanno scritto',
                      'nuovi messaggi radio', 'chi ha scritto mesh', 'messaggi radio',
                      'leggi lora', 'ci sono messaggi']):
            return '{"function_call": {"name": "leggi_messaggi_mesh"}}'

        # Nodi mesh vicini
        if match_any(['nodi vicini', 'nodi mesh', "chi c'è sulla mesh", 'dispositivi lora',
                      'quanti nodi', 'distanza nodi', 'stato mesh', 'rete mesh',
                      'chi è connesso', 'nodi lora', 'chi vedi sulla rete']):
            return '{"function_call": {"name": "nodi_mesh_vicini"}}'

        # ============ MEDITAZIONE ============
        if match_any(['meditazione', 'rilassamento', 'respirazione', 'mindfulness', 'rilassati']):
            return '{"function_call": {"name": "meditazione"}}'

        # ============ PODCAST ============
        if match_any(['podcast', 'ascolta podcast', 'metti podcast']):
            return '{"function_call": {"name": "podcast_italia", "arguments": {"action": "list"}}}'

        # ============ BEATBOX ============
        # Match diretto per beatbox - risposta immediata senza LLM
        if match_any(['beatbox', 'beat box', 'fai un beat', 'fammi un beat', 'fammi una base',
                      'base rap', 'base hip hop', 'base trap', 'boom tss', 'fai il rapper',
                      'beatboxing', 'fai beatbox', 'fai il beat', 'facciamo beatbox']):
            # Cerca stile specifico
            stili = {'hip hop': 'hip hop', 'hiphop': 'hip hop', 'trap': 'trap', 'dubstep': 'dubstep',
                     'drum and bass': 'drum and bass', 'dnb': 'drum and bass', 'reggaeton': 'reggaeton',
                     'freestyle': 'freestyle', 'techno': 'techno', 'jazz': 'jazz', 'italiano': 'italiano',
                     'robot': 'robot'}
            stile = ""
            for key, val in stili.items():
                if key in text_lower:
                    stile = val
                    break
            if stile:
                return f'{{"function_call": {{"name": "beatbox_umano", "arguments": {{"stile": "{stile}"}}}}}}'
            return '{"function_call": {"name": "beatbox_umano"}}'

        # ============ LOTTO ============
        if match_any(['lotto', 'estrazione', 'numeri lotto', 'superenalotto']):
            return '{"function_call": {"name": "lotto_estrazioni"}}'

        # ============ DADO ============
        if match_any(['lancia dado', 'tira dado', 'testa o croce', 'lancio moneta', 'd6', 'd20']):
            return '{"function_call": {"name": "dado"}}'

        # ============ CONVERTITORE ============
        if match_any(['converti', 'conversione', 'quanti km', 'quanti euro', 'fahrenheit', 'celsius']):
            return f'{{"function_call": {{"name": "convertitore", "arguments": {{"query": "{text}"}}}}}}'

        # ============ NUMERI UTILI ============
        if match_any(['numero telefono', 'numero utile', 'emergenza', 'carabinieri', 'polizia', 'ambulanza', '118', '112', '113']):
            return '{"function_call": {"name": "numeri_utili"}}'

        # ============ ACCADDE OGGI ============
        if match_any(['accadde oggi', 'cosa è successo oggi', 'eventi storici', 'questo giorno nella storia']):
            return '{"function_call": {"name": "accadde_oggi"}}'

        # ============ AGENDA ============
        if match_any(['agenda', 'appuntamento', 'calendario', 'cosa ho domani', 'prossimi impegni']):
            if match_any(['aggiungi', 'inserisci', 'metti']):
                return f'{{"function_call": {{"name": "agenda_eventi", "arguments": {{"action": "add", "titolo": "{text}"}}}}}}'
            return '{"function_call": {"name": "agenda_eventi", "arguments": {"action": "today"}}}'

        # ============ NOTE VOCALI ============
        if match_any(['nota vocale', 'prendi nota', 'annotazione', 'scrivi questo']):
            return f'{{"function_call": {{"name": "note_vocali", "arguments": {{"action": "add", "content": "{text}"}}}}}}'

        # ============ RUBRICA ============
        if match_any(['rubrica', 'numero di', 'telefono di', 'contatto']):
            return f'{{"function_call": {{"name": "rubrica_vocale", "arguments": {{"action": "search", "query": "{text}"}}}}}}'

        # ============ AIUTO PROFILO (Help vocale interattivo) ============
        # "aiuto", "help", "guida" -> mostra info profilo e comandi disponibili
        if match_any(['aiuto', 'help', 'guida vocale', 'come funziona', 'come si usa',
                      'istruzioni', 'quali comandi', 'cosa puoi fare per me']):
            # Aiuto specifico per una funzione?
            funzioni_aiuto = ['radio', 'meteo', 'timer', 'ricette', 'traduttore', 'quiz', 'barzelletta',
                             'promemoria', 'nota', 'spesa', 'musica', 'domotica', 'meditazione']
            for func in funzioni_aiuto:
                if func in text_lower:
                    return f'{{"function_call": {{"name": "aiuto_profilo", "arguments": {{"tipo": "funzione", "funzione": "{func}"}}}}}}'
            # Aiuto generale
            return '{"function_call": {"name": "aiuto_profilo", "arguments": {"tipo": "generale"}}}'

        # ============ SOMMARIO FUNZIONI & COME SI ATTIVA ============
        # Pattern: "come si attiva [qualcosa]", "come uso [qualcosa]", "come funziona [qualcosa]"
        import re
        attiva_patterns = [
            r'come (?:si )?attiva (?:la |il |lo |l\'|un |una )?(.+)',
            r'come (?:si )?usa (?:la |il |lo |l\'|un |una )?(.+)',
            r'come uso (?:la |il |lo |l\'|un |una )?(.+)',
            r'come funziona (?:la |il |lo |l\'|un |una )?(.+)',
            r'come faccio (?:a |ad )?(?:usare |attivare |aprire )?(?:la |il |lo |l\'|un |una )?(.+)',
            r'(?:come )?(?:si )?(?:attiva|usa|funziona) (.+)\?',
        ]
        for pattern in attiva_patterns:
            m = re.search(pattern, text_lower)
            if m:
                funzione = m.group(1).strip().rstrip('?')
                # Rimuovi parole comuni
                for word in ['funzione', 'la', 'il', 'lo', 'un', 'una', 'di', 'del', 'della']:
                    funzione = funzione.replace(word, '').strip()
                if funzione and len(funzione) > 1:
                    return f'{{"function_call": {{"name": "sommario_funzioni", "arguments": {{"funzione_specifica": "{funzione}"}}}}}}'

        # "cosa sai fare" va a CHI_SONO, qui solo richieste esplicite di elenco
        # Supporta richiesta per categoria specifica
        categorie_sommario = ['audio', 'media', 'giochi', 'gioco', 'informazioni', 'info', 'cucina', 'ricette',
                              'utilità', 'utility', 'traduzione', 'ricerca', 'benessere', 'casa', 'domotica',
                              'guide', 'bambini', 'famiglia', 'personalità', 'immagini', 'display']

        # Prima controlla se è una richiesta di categoria specifica: "funzionalità giochi", "quali giochi hai"
        for cat in categorie_sommario:
            if cat in text_lower and match_any(['funzionalita', 'funzionalità', 'funzioni', 'quali', 'elenco', 'lista']):
                cat_normalized = 'giochi' if cat == 'gioco' else cat
                return f'{{"function_call": {{"name": "sommario_funzioni", "arguments": {{"categoria": "{cat_normalized}"}}}}}}'

        # Poi controlla richieste generiche di elenco funzioni
        if match_any(['quali funzioni', 'elenco funzioni', 'lista funzioni', 'funzionalità disponibili',
                      'mostrami le funzioni', 'funzioni di', 'funzioni per', 'cosa fai con',
                      'elenco funzionalita', 'elenco funzionalità', 'lista funzionalita', 'lista funzionalità',
                      'che funzioni hai', 'che funzionalità hai', 'funzioni disponibili', 'help', 'aiuto']):
            return '{"function_call": {"name": "sommario_funzioni"}}'

        # ============ SUPPORTO EMOTIVO (ansia, paura - NON solitudine) ============
        if match_any(['ho paura', 'sono ansioso', 'ansia', 'panico', 'consolami', 'aiutami psicologicamente']):
            return f'{{"function_call": {{"name": "supporto_emotivo", "arguments": {{"stato": "{text}"}}}}}}'

        # ============ GIOCHI ============
        if match_any(['impiccato', 'giochiamo impiccato']):
            return '{"function_call": {"name": "impiccato", "arguments": {"action": "start"}}}'
        if match_any(['battaglia navale', 'affondare', 'navi']):
            return '{"function_call": {"name": "battaglia_navale", "arguments": {"action": "start"}}}'
        if match_any(['20 domande', 'venti domande', 'indovina cosa penso']):
            return '{"function_call": {"name": "venti_domande", "arguments": {"action": "start"}}}'
        if match_any(['chi vuol essere milionario', 'milionario']):
            return '{"function_call": {"name": "chi_vuol_essere", "arguments": {"action": "start"}}}'
        if match_any(['cruciverba', 'parole crociate']):
            return '{"function_call": {"name": "cruciverba_vocale", "arguments": {"action": "start"}}}'

        # ============ KARAOKE ============
        if match_any(['karaoke', 'cantiamo', 'testo canzone']):
            return f'{{"function_call": {{"name": "karaoke", "arguments": {{"query": "{text}"}}}}}}'

        # ============ ORACOLO ============
        if match_any(['oracolo', 'dimmi il futuro', 'previsione', 'cosa mi aspetta']):
            return f'{{"function_call": {{"name": "oracolo", "arguments": {{"domanda": "{text}"}}}}}}'

        # ============ COMPAGNO NOTTURNO ============
        if match_any(['non riesco a dormire', 'insonnia', 'compagnia stanotte', 'ho incubi']):
            return '{"function_call": {"name": "compagno_notturno"}}'

        # ============ CERCA MUSICA (YouTube) - DISABILITATO, usiamo solo radio ============
        # if match_any(['suona', 'metti la canzone', 'cerca musica', 'fammi sentire', 'play music']):
        #     return f'{{"function_call": {{"name": "cerca_musica", "arguments": {{"query": "{text}"}}}}}}'

        # ============ GUIDA TURISTICA ============
        if match_any(['guida turistica', 'cosa visitare', 'monumenti', 'turismo', 'luoghi da vedere']):
            return f'{{"function_call": {{"name": "guida_turistica", "arguments": {{"location": "{text}"}}}}}}'

        # ============ GUIDA RISTORANTI ============
        if match_any(['ristorante', 'dove mangiare', 'pizzeria', 'trattoria', 'consigliami un locale']):
            return f'{{"function_call": {{"name": "guida_ristoranti", "arguments": {{"query": "{text}"}}}}}}'

        # ============ WEB SEARCH (DuckDuckGo) ============
        # Pattern ampi per ricerche web
        if match_any(['cerca su internet', 'cerca online', 'google', 'ricerca web', 'cerca su google',
                      'cercami', 'puoi cercare', 'fammi una ricerca', 'trova informazioni', 'cerca info',
                      'risultati per', 'trova su internet']):
            # Estrai query rimuovendo prefissi
            query = text_lower
            for prefix in ['cerca su internet', 'cerca online', 'cerca su google', 'cercami',
                          'puoi cercare', 'fammi una ricerca', 'trova informazioni su',
                          'trova informazioni', 'google', 'cerca info su', 'cerca info']:
                query = query.replace(prefix, '').strip()
            return f'{{"function_call": {{"name": "web_search", "arguments": {{"query": "{query or text}"}}}}}}'

        # ============ RISPOSTA AI (usa Groq LLM esistente) ============
        # Pattern per richieste AI/IA - tutte le varianti di chatbot
        if match_any(['chiedi a gpt', 'chiedi a chatgpt', 'chiedi a gemini', 'chiedi a grok',
                      'chiedi a claude', 'chiedi a copilot', 'chiedi a bard', 'chiedi a llama',
                      'cerca con ai', 'cerca con ia', 'cerca con gpt', 'cerca con chatgpt',
                      'cerca con gemini', 'cerca con grok', 'cerca con claude', 'cerca con copilot',
                      'domanda a gpt', 'domanda a gemini', 'domanda ai', 'domanda ia',
                      'rispondi con ai', 'rispondi con ia', 'usa ai', 'usa ia',
                      "chiedi all'ai", "chiedi all'ia", "chiedi all'intelligenza"]):
            # Estrai la domanda rimuovendo il prefisso
            domanda = text_lower
            for prefix in ['chiedi a gpt', 'chiedi a chatgpt', 'chiedi a gemini', 'chiedi a grok',
                          'chiedi a claude', 'cerca con ai', 'cerca con ia', 'cerca con gpt',
                          'domanda a gpt', 'domanda ai', 'domanda ia', 'rispondi con ai',
                          'usa ai', 'usa ia', "chiedi all'ai", "chiedi all'ia"]:
                domanda = domanda.replace(prefix, '').strip()
            return f'{{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "{domanda or text}"}}}}}}'

        # ============ CHI SONO (Identità chatbot) - PRIMA di "parlami di" generico! ============
        if match_any(['chi sei', 'come ti chiami', 'tu chi sei', 'presentati', 'cosa sai fare',
                      'cosa sei', 'parlami di te', 'chi sei tu', 'dimmi chi sei']):
            return '{"function_call": {"name": "chi_sono"}}'

        # Domande generiche che richiedono intelligenza artificiale
        # NOTA: "parlami di te" è già gestito sopra da CHI_SONO
        if match_any(["cos'è", "cosa è", "chi è", "cosa significa", "cosa vuol dire", "spiegami",
                      "dimmi cos'è", "sai cos'è", "informazioni su", "descrivi",
                      "come funziona", "perché", "perche", "qual è la differenza", "confronta"]):
            return f'{{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "{text}"}}}}}}'

        # ============ PERSONALITÀ MULTIPLE ============
        # Lista personalità disponibili
        if match_any(['lista personalita', 'lista personalità', 'elenco personalita', 'elenco personalità',
                      'quali personalita', 'quali personalità', 'personalità disponibili', 'che personalità hai',
                      'che voci hai', 'quali voci hai', 'quali personaggi', 'personaggi disponibili']):
            return '{"function_call": {"name": "personalita_multiple", "arguments": {"personalita": "lista"}}}'

        # SOLO se c'è una keyword specifica di personalità, altrimenti non matchare
        personalita_keywords = ['pirata', 'robot', 'nonno', 'maggiordomo', 'bambino', 'poeta',
                               'complottista', 'nonna', 'filosofo', 'ubriaco', 'ubriaca', 'brillo', 'sbronzo', 'sbronza']
        # Controlla PRIMA se c'è una keyword di personalità
        for pers in personalita_keywords:
            if pers in text_lower:
                # Normalizza ubriaca -> ubriaco, sbronza -> sbronzo
                pers_normalized = pers.replace('ubriaca', 'ubriaco').replace('sbronza', 'sbronzo')
                # Pattern semplice: solo la keyword (es. "ubriaca", "pirata")
                # Se il testo è breve (<20 char) o contiene "fai" generico, attiva
                is_simple = len(text.strip()) < 20 or 'fai' in text_lower
                # E poi se c'è un trigger appropriato O è una richiesta semplice
                if is_simple or match_any(['trasformati in', 'parla come', 'diventa un', 'fai il', 'fai la', 'modalità',
                             'cambia personalità', 'voce da', 'come un', 'essere un', 'parla da']):
                    return f'{{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "{pers_normalized}"}}}}}}'
        if match_any(['torna normale', 'basta personalità', 'smetti di fare', 'torna te stesso']):
            return '{"function_call": {"name": "personalita_multiple", "arguments": {"personalita": "normale"}}}'

        # ============ COMPAGNO ANTI-SOLITUDINE ============
        if match_any(['mi sento solo', 'fammi compagnia', 'sono triste', 'nessuno mi parla',
                      'ho bisogno di compagnia', 'parliamo un po', 'tienimi compagnia', 'chiacchieriamo']):
            return '{"function_call": {"name": "compagno_antisolitudine"}}'

        # ============ EASTER EGG FOLLI ============
        if match_any(['insultami', 'dimmi qualcosa di cattivo', 'offendimi']):
            return '{"function_call": {"name": "easter_egg_folli", "arguments": {"tipo": "insulto"}}}'
        if match_any(['confessami', 'ho peccato', 'devo confessare']):
            return '{"function_call": {"name": "easter_egg_folli", "arguments": {"tipo": "confessione"}}}'
        if match_any(['litiga con te stesso', 'litiga con te stessa', 'litiga con se stesso', 'litiga con se stessa',
                      'fai casino', 'fai il pazzo', 'fai la pazza', 'litigate', 'litiga', 'litigare']):
            return '{"function_call": {"name": "easter_egg_folli", "arguments": {"tipo": "litigio"}}}'
        if match_any(['dimmi una profezia', 'predici il futuro', 'cosa mi succederà']):
            return '{"function_call": {"name": "easter_egg_folli", "arguments": {"tipo": "profezia"}}}'

        # ============ SUONI AMBIENTE / ASMR ============
        suoni_keywords = ['pioggia', 'temporale', 'onde', 'mare', 'foresta', 'bosco', 'camino',
                         'fuoco', 'ruscello', 'vento', 'notte', 'grilli', 'rumore bianco',
                         'battito', 'cuore', 'caffetteria', 'treno']
        if match_any(['suoni rilassanti', 'rumore bianco', 'asmr', 'suoni natura',
                      'aiutami a dormire', 'suoni per dormire', 'ambiente rilassante', 'suono del']):
            for suono in suoni_keywords:
                if suono in text_lower:
                    return f'{{"function_call": {{"name": "suoni_ambiente", "arguments": {{"suono": "{suono}"}}}}}}'
            return '{"function_call": {"name": "suoni_ambiente"}}'
        # Match diretto suoni
        for suono in suoni_keywords:
            if f'suono {suono}' in text_lower or f'metti {suono}' in text_lower or f'fammi sentire {suono}' in text_lower:
                return f'{{"function_call": {{"name": "suoni_ambiente", "arguments": {{"suono": "{suono}"}}}}}}'

        # ============ VERSI ANIMALI ============
        animali = ['gallo', 'gallina', 'mucca', 'maiale', 'asino', 'pecora', 'capra', 'anatra', 'oca', 'tacchino', 'cavallo', 'cane', 'gatto']
        # Match diretto per animale - PRIMA controlla se c'è un animale specifico
        for animale in animali:
            if animale in text_lower:
                if match_any(['fai il verso', 'verso del', 'come fa', 'imita', 'fai il']):
                    return f'{{"function_call": {{"name": "versi_animali", "arguments": {{"animale": "{animale}"}}}}}}'
        # Pattern generici solo se espliciti
        if match_any(['fai il verso', 'imita un animale', 'animali da cortile', 'fai coccodè', 'fai muuu', 'fai bau', 'chicchirichì']):
            return '{"function_call": {"name": "versi_animali"}}'

        # ============ BEATBOX UMANO ============
        if match_any(['beatbox', 'fai un beat', 'fammi un beat', 'base rap', 'base trap', 'boom tss',
                      'fai il rapper', 'beatboxing', 'fammi una base', 'beat hip hop', 'beat dubstep']):
            stili = ['hip hop', 'trap', 'dubstep', 'drum', 'reggaeton', 'freestyle', 'techno', 'jazz', 'italiano', 'robot']
            stile_match = next((s for s in stili if s in text_lower), "")
            if stile_match:
                return f'{{"function_call": {{"name": "beatbox_umano", "arguments": {{"stile": "{stile_match}"}}}}}}'
            return '{"function_call": {"name": "beatbox_umano"}}'

        # ============ COOKING COMPANION (Guida Cucina Passo-Passo) ============
        if match_any(['cuciniamo', 'guidami in cucina', 'passo passo', 'step successivo', 'prossimo step',
                      'avanti con la ricetta', 'ripeti lo step', 'aiutami a cucinare', 'cucina con me']):
            if match_any(['avanti', 'prossimo', 'next', 'continua']):
                return '{"function_call": {"name": "cooking_companion", "arguments": {"azione": "avanti"}}}'
            if match_any(['ripeti', 'ancora', 'non ho capito']):
                return '{"function_call": {"name": "cooking_companion", "arguments": {"azione": "ripeti"}}}'
            if match_any(['ingredienti', 'cosa serve', 'cosa mi serve']):
                return '{"function_call": {"name": "cooking_companion", "arguments": {"azione": "ingredienti"}}}'
            if match_any(['stop', 'basta', 'finito']):
                return '{"function_call": {"name": "cooking_companion", "arguments": {"azione": "stop"}}}'
            # Estrai nome ricetta
            ricetta_match = re.search(r'(?:cuciniamo|prepariamo|facciamo)\s+(?:la\s+)?(.+?)(?:\?|$)', text_lower)
            ricetta = ricetta_match.group(1) if ricetta_match else ""
            return f'{{"function_call": {{"name": "cooking_companion", "arguments": {{"ricetta": "{ricetta}"}}}}}}'

        # ============ FALLBACK: RISPOSTA AI (Groq LLM) ============
        # Se nessun pattern specifico ha matchato, usa l'AI per rispondere
        # Questo permette conversazioni fluide anche senza trigger specifici
        logger.bind(tag=TAG).debug(f"Nessun pattern matchato, fallback a risposta_ai: {text[:50]}...")
        return f'{{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "{text}"}}}}}}'
