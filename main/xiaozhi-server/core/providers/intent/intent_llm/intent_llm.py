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

        # ============ RADIO ============
        if match_any(['sintonizza', 'metti radio', 'ascolta radio', 'accendi radio']) or \
           (match_any(['radio']) and match_any(['deejay', 'zeta', 'capital', 'm2o', 'italia', 'rai', '105', 'virgin', 'kiss', 'rtl'])):
            station_match = re.search(r'radio\s*(\w+)', text_lower)
            station = station_match.group(0) if station_match else ""
            if match_any(['elenco', 'lista', 'quali radio']):
                return '{"function_call": {"name": "radio_italia", "arguments": {"action": "list"}}}'
            elif match_any(['stop', 'ferma', 'spegni']):
                return '{"function_call": {"name": "radio_italia", "arguments": {"action": "stop"}}}'
            result = f'{{"function_call": {{"name": "radio_italia", "arguments": {{"action": "play", "station": "{station}"}}}}}}'
            logger.bind(tag=TAG).debug(f"Pre-check: radio -> {result}")
            return result

        # ============ METEO ============
        if match_any(['che tempo fa', 'meteo', 'previsioni', 'piove', 'temperatura', 'come sarà il tempo']):
            city_match = re.search(r'(?:a|di|per|su)\s+(\w+)', text_lower)
            city = city_match.group(1) if city_match else ""
            result = f'{{"function_call": {{"name": "meteo_italia", "arguments": {{"city": "{city}"}}}}}}'
            logger.bind(tag=TAG).debug(f"Pre-check: meteo -> {result}")
            return result

        # ============ NOTIZIE ============
        if match_any(['notizie', 'ultime news', 'cosa succede', 'telegiornale', 'rassegna stampa']):
            return '{"function_call": {"name": "notizie_italia", "arguments": {"action": "headlines"}}}'

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
        if 'giannini' in text_lower or 'giannino' in text_lower:
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
        lingue_trad = ['inglese', 'francese', 'spagnolo', 'tedesco', 'portoghese', 'russo', 'cinese', 'giapponese', 'arabo', 'greco', 'olandese', 'polacco']
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

        # ============ MEDITAZIONE ============
        if match_any(['meditazione', 'rilassamento', 'respirazione', 'mindfulness', 'rilassati']):
            return '{"function_call": {"name": "meditazione"}}'

        # ============ PODCAST ============
        if match_any(['podcast', 'ascolta podcast', 'metti podcast']):
            return '{"function_call": {"name": "podcast_italia", "arguments": {"action": "list"}}}'

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

        # ============ SOMMARIO FUNZIONI ============
        # "cosa sai fare" va a CHI_SONO, qui solo richieste esplicite di elenco
        # Supporta richiesta per categoria specifica
        categorie_sommario = ['audio', 'media', 'giochi', 'informazioni', 'info', 'cucina', 'ricette',
                              'utilità', 'utility', 'traduzione', 'ricerca', 'benessere', 'casa', 'domotica',
                              'guide', 'bambini', 'famiglia', 'personalità']
        if match_any(['quali funzioni', 'elenco funzioni', 'lista funzioni', 'help', 'funzionalità disponibili',
                      'mostrami le funzioni', 'funzioni di', 'funzioni per', 'cosa fai con']):
            # Cerca se c'è una categoria specifica
            for cat in categorie_sommario:
                if cat in text_lower:
                    return f'{{"function_call": {{"name": "sommario_funzioni", "arguments": {{"categoria": "{cat}"}}}}}}'
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
        # SOLO se c'è una keyword specifica di personalità, altrimenti non matchare
        personalita_keywords = ['pirata', 'robot', 'nonno', 'maggiordomo', 'bambino', 'poeta',
                               'complottista', 'nonna', 'filosofo', 'ubriaco', 'brillo', 'sbronzo']
        # Controlla PRIMA se c'è una keyword di personalità
        for pers in personalita_keywords:
            if pers in text_lower:
                # E poi se c'è un trigger appropriato
                if match_any(['trasformati in', 'parla come', 'diventa un', 'fai il', 'modalità',
                             'cambia personalità', 'voce da', 'come un', 'essere un']):
                    return f'{{"function_call": {{"name": "personalita_multiple", "arguments": {{"personalita": "{pers}"}}}}}}'
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
        if match_any(['litiga con te stesso', 'fai casino', 'fai il pazzo']):
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
        # Questo evita di passare all'LLM per il riconoscimento intent
        logger.bind(tag=TAG).debug(f"Nessun pattern matchato, fallback a risposta_ai: {text[:50]}...")
        return f'{{"function_call": {{"name": "risposta_ai", "arguments": {{"domanda": "{text}"}}}}}}'

        # 记录整体开始时间
        total_start_time = time.time()

        # 打印使用的模型信息
        model_info = getattr(self.llm, "model_name", str(self.llm.__class__.__name__))
        logger.bind(tag=TAG).debug(f"使用意图识别模型: {model_info}")

        # 计算缓存键
        cache_key = hashlib.md5((conn.device_id + text).encode()).hexdigest()

        # 检查缓存
        cached_intent = self.cache_manager.get(self.CacheType.INTENT, cache_key)
        if cached_intent is not None:
            cache_time = time.time() - total_start_time
            logger.bind(tag=TAG).debug(
                f"使用缓存的意图: {cache_key} -> {cached_intent}, 耗时: {cache_time:.4f}秒"
            )
            return cached_intent

        if self.promot == "":
            functions = conn.func_handler.get_functions()
            if hasattr(conn, "mcp_client"):
                mcp_tools = conn.mcp_client.get_available_tools()
                if mcp_tools is not None and len(mcp_tools) > 0:
                    if functions is None:
                        functions = []
                    functions.extend(mcp_tools)

            self.promot = self.get_intent_system_prompt(functions)

        music_config = initialize_music_handler(conn)
        music_file_names = music_config["music_file_names"]
        prompt_music = f"{self.promot}\n<musicNames>{music_file_names}\n</musicNames>"

        home_assistant_cfg = conn.config["plugins"].get("home_assistant")
        if home_assistant_cfg:
            devices = home_assistant_cfg.get("devices", [])
        else:
            devices = []
        if len(devices) > 0:
            hass_prompt = "\n下面是我家智能设备列表（位置，设备名，entity_id），可以通过homeassistant控制\n"
            for device in devices:
                hass_prompt += device + "\n"
            prompt_music += hass_prompt

        logger.bind(tag=TAG).debug(f"User prompt: {prompt_music}")

        # 构建用户对话历史的提示
        msgStr = ""

        # 获取最近的对话历史
        start_idx = max(0, len(dialogue_history) - self.history_count)
        for i in range(start_idx, len(dialogue_history)):
            msgStr += f"{dialogue_history[i].role}: {dialogue_history[i].content}\n"

        msgStr += f"User: {text}\n"
        user_prompt = f"current dialogue:\n{msgStr}"

        # 记录预处理完成时间
        preprocess_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(f"意图识别预处理耗时: {preprocess_time:.4f}秒")

        # 使用LLM进行意图识别
        llm_start_time = time.time()
        logger.bind(tag=TAG).debug(f"开始LLM意图识别调用, 模型: {model_info}")

        intent = self.llm.response_no_stream(
            system_prompt=prompt_music, user_prompt=user_prompt
        )

        # 记录LLM调用完成时间
        llm_time = time.time() - llm_start_time
        logger.bind(tag=TAG).debug(
            f"外挂的大模型意图识别完成, 模型: {model_info}, 调用耗时: {llm_time:.4f}秒"
        )

        # 记录后处理开始时间
        postprocess_start_time = time.time()

        # 清理和解析响应
        intent = intent.strip()
        # 尝试提取JSON部分
        match = re.search(r"\{.*\}", intent, re.DOTALL)
        if match:
            intent = match.group(0)

        # 记录总处理时间
        total_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(
            f"【意图识别性能】模型: {model_info}, 总耗时: {total_time:.4f}秒, LLM调用: {llm_time:.4f}秒, 查询: '{text[:20]}...'"
        )

        # 尝试解析为JSON
        try:
            intent_data = json.loads(intent)
            # 如果包含function_call，则格式化为适合处理的格式
            if "function_call" in intent_data:
                function_data = intent_data["function_call"]
                function_name = function_data.get("name")
                function_args = function_data.get("arguments", {})

                # 记录识别到的function call
                logger.bind(tag=TAG).info(
                    f"llm 识别到意图: {function_name}, 参数: {function_args}"
                )

                # 处理不同类型的意图
                if function_name == "result_for_context":
                    # 处理基础信息查询，直接从context构建结果
                    logger.bind(tag=TAG).info(
                        "检测到result_for_context意图，将使用上下文信息直接回答"
                    )

                elif function_name == "continue_chat":
                    # 处理普通对话
                    # 保留非工具相关的消息
                    clean_history = [
                        msg
                        for msg in conn.dialogue.dialogue
                        if msg.role not in ["tool", "function"]
                    ]
                    conn.dialogue.dialogue = clean_history

                else:
                    # 处理函数调用
                    logger.bind(tag=TAG).info(f"检测到函数调用意图: {function_name}")

            # 统一缓存处理和返回
            self.cache_manager.set(self.CacheType.INTENT, cache_key, intent)
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).debug(f"意图后处理耗时: {postprocess_time:.4f}秒")
            return intent
        except json.JSONDecodeError:
            # 后处理时间
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).error(
                f"无法解析意图JSON: {intent}, 后处理耗时: {postprocess_time:.4f}秒"
            )
            # Fallback: usa risposta_intelligente per dare comunque una risposta vocale
            # invece di bloccarsi su continue_chat che può non rispondere
            logger.bind(tag=TAG).info(
                f"Fallback: uso risposta_intelligente per: {text[:50]}..."
            )
            return f'{{"function_call": {{"name": "risposta_intelligente", "arguments": {{"domanda": "{text}"}}}}}}'
