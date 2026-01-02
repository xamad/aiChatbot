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
        if match_any(['barzelletta', 'battuta', 'raccontami una', 'fammi ridere']):
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

        # ============ PROMEMORIA ============
        if match_any(['ricordami', 'promemoria', 'ricorda di', 'non dimenticare']):
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

        # ============ GIANNINO (Easter Egg) ============
        if 'giannino' in text_lower:
            return f'{{"function_call": {{"name": "giannino_easter_egg", "arguments": {{"domanda": "{text}"}}}}}}'

        # ============ RICETTE ============
        if match_any(['ricetta', 'come si fa', 'come si cucina', 'ingredienti', 'prepara']):
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
        if match_any(['curiosità', 'lo sapevi', 'fatto interessante', 'dimmi qualcosa']):
            return '{"function_call": {"name": "curiosita"}}'

        # ============ FRASE DEL GIORNO ============
        if match_any(['frase del giorno', 'citazione', 'frase motivazionale', 'ispirami']):
            return '{"function_call": {"name": "frase_del_giorno"}}'

        # ============ TRADUTTORE ============
        if match_any(['traduci', 'traduzione', 'come si dice', 'in inglese', 'in francese', 'in spagnolo', 'in tedesco']):
            return f'{{"function_call": {{"name": "traduttore", "arguments": {{"text": "{text}"}}}}}}'

        # ============ LISTA SPESA ============
        if match_any(['lista spesa', 'lista della spesa', 'aggiungi alla spesa', 'cosa devo comprare']):
            if match_any(['aggiungi', 'metti', 'inserisci']):
                return f'{{"function_call": {{"name": "lista_spesa", "arguments": {{"action": "add", "item": "{text}"}}}}}}'
            return '{"function_call": {"name": "lista_spesa", "arguments": {"action": "list"}}}'

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
        if match_any(['cosa sai fare', 'quali funzioni', 'aiuto', 'help', 'cosa puoi fare', 'funzionalità']):
            return '{"function_call": {"name": "sommario_funzioni"}}'

        # ============ SUPPORTO EMOTIVO ============
        if match_any(['sono triste', 'mi sento solo', 'ho paura', 'sono ansioso', 'consolami', 'supporto']):
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

        # ============ CERCA MUSICA (YouTube) ============
        if match_any(['suona', 'metti la canzone', 'cerca musica', 'fammi sentire', 'play music']):
            return f'{{"function_call": {{"name": "cerca_musica", "arguments": {{"query": "{text}"}}}}}}'

        # ============ GUIDA TURISTICA ============
        if match_any(['guida turistica', 'cosa visitare', 'monumenti', 'turismo', 'luoghi da vedere']):
            return f'{{"function_call": {{"name": "guida_turistica", "arguments": {{"location": "{text}"}}}}}}'

        # ============ GUIDA RISTORANTI ============
        if match_any(['ristorante', 'dove mangiare', 'pizzeria', 'trattoria', 'consigliami un locale']):
            return f'{{"function_call": {{"name": "guida_ristoranti", "arguments": {{"query": "{text}"}}}}}}'

        # ============ WEB SEARCH ============
        if match_any(['cerca su internet', 'cerca online', 'google', 'ricerca web']):
            return f'{{"function_call": {{"name": "web_search", "arguments": {{"query": "{text}"}}}}}}'

        # ============ CHI SONO (Identità chatbot) ============
        if match_any(['chi sei', 'come ti chiami', 'tu chi sei', 'presentati', 'cosa sai fare', 'cosa sei', 'parlami di te', 'chi sei tu', 'dimmi chi sei']):
            return '{"function_call": {"name": "chi_sono"}}'

        # ============ VERSI ANIMALI ============
        animali = ['gallo', 'gallina', 'mucca', 'maiale', 'asino', 'pecora', 'capra', 'anatra', 'oca', 'tacchino', 'cavallo', 'cane', 'gatto']
        if match_any(['fai il verso', 'imita animale', 'come fa il', 'verso del', 'fai l\'animale', 'animali da cortile',
                      'fai coccodè', 'fai muuu', 'fai bau', 'chicchirichì', 'fammi sentire']):
            # Cerca animale specifico
            animale_match = next((a for a in animali if a in text_lower), "")
            if animale_match:
                return f'{{"function_call": {{"name": "versi_animali", "arguments": {{"animale": "{animale_match}"}}}}}}'
            return '{"function_call": {"name": "versi_animali"}}'
        # Match diretto per animale
        for animale in animali:
            if f'fai il {animale}' in text_lower or f'come fa il {animale}' in text_lower or f'imita il {animale}' in text_lower:
                return f'{{"function_call": {{"name": "versi_animali", "arguments": {{"animale": "{animale}"}}}}}}'

        # ============ RICETTE CON INGREDIENTI ============
        if match_any(['cosa posso cucinare', 'ricette con', 'ho in casa', 'cosa preparo con', 'che piatto faccio con', 'idee ricette']):
            # Estrai ingredienti
            ing_match = re.search(r'(?:con|ho)\s+(.+?)(?:\?|$)', text_lower)
            ingredienti = ing_match.group(1) if ing_match else text
            return f'{{"function_call": {{"name": "ricette_ingredienti", "arguments": {{"ingredienti": "{ingredienti}"}}}}}}'

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
            # Fallback: usa web_search per dare comunque una risposta vocale
            # invece di bloccarsi su continue_chat che può non rispondere
            logger.bind(tag=TAG).info(
                f"Fallback: uso web_search per rispondere a: {text[:50]}..."
            )
            return f'{{"function_call": {{"name": "web_search", "arguments": {{"query": "{text}"}}}}}}'
