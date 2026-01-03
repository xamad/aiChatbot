"""
Cooking Companion - Assistente cucina hands-free
Ricette passo-passo, timer multipli, suggerimenti
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from urllib.parse import quote
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File stato cucina
COOKING_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cooking_state.json")

# Timer attivi (in memoria)
_timer_attivi = {}

# Ricetta corrente in corso
_ricetta_corrente = None
_step_corrente = 0


def load_cooking_state() -> dict:
    """Carica stato cucina"""
    default = {"ricetta_corrente": None, "step": 0, "timer": [], "storico": []}
    try:
        if os.path.exists(COOKING_STATE_FILE):
            with open(COOKING_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento stato: {e}")
    return default


def save_cooking_state(data: dict):
    """Salva stato cucina"""
    try:
        os.makedirs(os.path.dirname(COOKING_STATE_FILE), exist_ok=True)
        with open(COOKING_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio: {e}")


# Database ricette comuni con step dettagliati
RICETTE_GUIDATE = {
    "pasta_pomodoro": {
        "nome": "Pasta al Pomodoro",
        "tempo_totale": "20 minuti",
        "porzioni": 4,
        "ingredienti": [
            "400g pasta",
            "400g pomodori pelati",
            "2 spicchi aglio",
            "basilico fresco",
            "olio extravergine",
            "sale, pepe"
        ],
        "steps": [
            {"testo": "Metti una pentola grande con acqua sul fuoco. Quando bolle, sala abbondantemente.", "timer": None, "attesa": "bollitura"},
            {"testo": "Intanto, in una padella, scalda 4 cucchiai d'olio con gli spicchi d'aglio schiacciati a fuoco medio.", "timer": 120, "attesa": None},
            {"testo": "Quando l'aglio è dorato, togli l'aglio e aggiungi i pomodori pelati. Schiaccia con una forchetta.", "timer": None, "attesa": None},
            {"testo": "Lascia cuocere il sugo a fuoco medio per 15 minuti, mescolando ogni tanto.", "timer": 900, "attesa": None},
            {"testo": "Butta la pasta nell'acqua bollente. Cuoci per il tempo indicato sulla confezione meno 1 minuto.", "timer": 540, "attesa": None},
            {"testo": "Scola la pasta tenendo da parte un mestolo di acqua di cottura.", "timer": None, "attesa": None},
            {"testo": "Versa la pasta nella padella col sugo. Aggiungi un po' di acqua di cottura e manteca per 1 minuto a fuoco vivo.", "timer": 60, "attesa": None},
            {"testo": "Spegni il fuoco, aggiungi basilico fresco e un filo d'olio a crudo. Pronto!", "timer": None, "attesa": None}
        ]
    },

    "carbonara": {
        "nome": "Carbonara",
        "tempo_totale": "25 minuti",
        "porzioni": 4,
        "ingredienti": [
            "400g spaghetti o rigatoni",
            "200g guanciale",
            "4 tuorli + 1 uovo intero",
            "100g pecorino romano",
            "pepe nero"
        ],
        "steps": [
            {"testo": "Metti l'acqua a bollire per la pasta. Taglia il guanciale a listarelle di circa mezzo centimetro.", "timer": None, "attesa": "bollitura"},
            {"testo": "In una ciotola, sbatti i tuorli con l'uovo intero, aggiungi il pecorino grattugiato e abbondante pepe. Mescola bene.", "timer": None, "attesa": None},
            {"testo": "In una padella fredda metti il guanciale. Accendi a fuoco medio-basso e fai sciogliere il grasso lentamente.", "timer": 480, "attesa": None},
            {"testo": "Il guanciale deve diventare croccante fuori ma morbido dentro. Spegni e tieni da parte.", "timer": None, "attesa": None},
            {"testo": "Butta la pasta nell'acqua bollente salata. Cuoci al dente.", "timer": 600, "attesa": None},
            {"testo": "Scola la pasta tenendo da parte mezzo bicchiere di acqua di cottura.", "timer": None, "attesa": None},
            {"testo": "IMPORTANTE: Spegni il fuoco! Versa la pasta nella padella col guanciale, mescola.", "timer": None, "attesa": None},
            {"testo": "Fuori dal fuoco, versa il composto di uova e pecorino. Mescola velocemente aggiungendo acqua di cottura se troppo denso.", "timer": None, "attesa": None},
            {"testo": "Servi subito con altro pecorino e pepe. La cremina deve essere lucida, non strapazzata!", "timer": None, "attesa": None}
        ]
    },

    "risotto_parmigiano": {
        "nome": "Risotto alla Parmigiana",
        "tempo_totale": "25 minuti",
        "porzioni": 4,
        "ingredienti": [
            "320g riso carnaroli",
            "1 litro brodo vegetale caldo",
            "1 cipolla piccola",
            "80g burro",
            "100g parmigiano",
            "mezzo bicchiere vino bianco"
        ],
        "steps": [
            {"testo": "Trita finemente la cipolla. Tieni il brodo caldo in un pentolino a parte.", "timer": None, "attesa": None},
            {"testo": "In una casseruola larga, sciogli metà del burro e fai appassire la cipolla a fuoco dolce per 5 minuti.", "timer": 300, "attesa": None},
            {"testo": "Aggiungi il riso e tostalo per 2 minuti mescolando. Deve diventare traslucido ai bordi.", "timer": 120, "attesa": None},
            {"testo": "Sfuma con il vino bianco e lascia evaporare completamente.", "timer": 60, "attesa": None},
            {"testo": "Inizia ad aggiungere il brodo caldo, un mestolo alla volta. Mescola spesso.", "timer": None, "attesa": None},
            {"testo": "Continua per circa 16-18 minuti aggiungendo brodo quando si asciuga. Il riso deve restare all'onda.", "timer": 960, "attesa": None},
            {"testo": "Spegni il fuoco. Aggiungi il burro freddo rimasto e il parmigiano. Manteca vigorosamente.", "timer": None, "attesa": None},
            {"testo": "Copri e lascia riposare 2 minuti. Servi subito, il risotto deve essere cremoso e fluido!", "timer": 120, "attesa": None}
        ]
    },

    "frittata": {
        "nome": "Frittata Classica",
        "tempo_totale": "15 minuti",
        "porzioni": 2,
        "ingredienti": [
            "4 uova",
            "2 cucchiai parmigiano",
            "sale, pepe",
            "olio o burro",
            "(opzionale: verdure, formaggio, salumi)"
        ],
        "steps": [
            {"testo": "Rompi le uova in una ciotola. Aggiungi sale, pepe e parmigiano. Sbatti bene con una forchetta.", "timer": None, "attesa": None},
            {"testo": "Scalda una padella antiaderente con un filo d'olio o una noce di burro a fuoco medio.", "timer": 60, "attesa": None},
            {"testo": "Versa le uova sbattute nella padella calda. Lascia cuocere senza mescolare.", "timer": None, "attesa": None},
            {"testo": "Quando i bordi si staccano e il centro è quasi rappreso, copri con un coperchio per 3 minuti a fuoco basso.", "timer": 180, "attesa": None},
            {"testo": "Gira la frittata usando un piatto o il coperchio. Cuoci l'altro lato per 2 minuti.", "timer": 120, "attesa": None},
            {"testo": "Pronta! Servi calda o anche tiepida, è buona comunque!", "timer": None, "attesa": None}
        ]
    },

    "caffe_moka": {
        "nome": "Caffè con la Moka",
        "tempo_totale": "5 minuti",
        "porzioni": "2-3 tazzine",
        "ingredienti": [
            "caffè macinato per moka",
            "acqua"
        ],
        "steps": [
            {"testo": "Riempi la caldaia con acqua fredda fino alla valvola, non oltre!", "timer": None, "attesa": None},
            {"testo": "Inserisci il filtro e riempilo di caffè. Non pressare, livella solo con il dito.", "timer": None, "attesa": None},
            {"testo": "Avvita bene la parte superiore e metti sul fuoco medio-basso.", "timer": None, "attesa": None},
            {"testo": "Tieni il coperchio aperto per controllare. Quando inizia a uscire il caffè...", "timer": 120, "attesa": None},
            {"testo": "Appena senti il gorgoglio, spegni subito! Il caffè continuerà a salire col calore residuo.", "timer": None, "attesa": None},
            {"testo": "Mescola il caffè nella moka per amalgamare e servi. Perfetto!", "timer": None, "attesa": None}
        ]
    },

    "uova_strapazzate": {
        "nome": "Uova Strapazzate Cremose",
        "tempo_totale": "10 minuti",
        "porzioni": 2,
        "ingredienti": [
            "4 uova",
            "20g burro",
            "sale, pepe",
            "(opzionale: erba cipollina)"
        ],
        "steps": [
            {"testo": "Rompi le uova in una ciotola, aggiungi un pizzico di sale. NON sbatterle ancora.", "timer": None, "attesa": None},
            {"testo": "Metti una padella antiaderente a fuoco BASSO con il burro.", "timer": None, "attesa": None},
            {"testo": "Versa le uova nella padella col burro sciolto. Ora inizia a mescolare lentamente con una spatola.", "timer": None, "attesa": None},
            {"testo": "Mescola continuamente portando i bordi verso il centro. Fuoco sempre basso!", "timer": 180, "attesa": None},
            {"testo": "Quando sono cremose ma ancora umide, SPEGNI. Continueranno a cuocere col calore.", "timer": None, "attesa": None},
            {"testo": "Servi subito su pane tostato. Devono essere morbide, non secche!", "timer": None, "attesa": None}
        ]
    }
}

# Keywords per trovare ricette
RICETTA_KEYWORDS = {
    "pasta": "pasta_pomodoro",
    "pomodoro": "pasta_pomodoro",
    "spaghetti pomodoro": "pasta_pomodoro",
    "carbonara": "carbonara",
    "guanciale": "carbonara",
    "risotto": "risotto_parmigiano",
    "parmigiana": "risotto_parmigiano",
    "frittata": "frittata",
    "uova frittata": "frittata",
    "caffè": "caffe_moka",
    "caffe": "caffe_moka",
    "moka": "caffe_moka",
    "uova strapazzate": "uova_strapazzate",
    "strapazzate": "uova_strapazzate",
    "scrambled": "uova_strapazzate",
}


def trova_ricetta(nome: str) -> tuple:
    """Trova ricetta per nome"""
    if not nome:
        return None, None

    nome_lower = nome.lower()

    for keyword, ricetta_key in RICETTA_KEYWORDS.items():
        if keyword in nome_lower:
            return ricetta_key, RICETTE_GUIDATE[ricetta_key]

    return None, None


def format_step(ricetta: dict, step_num: int) -> tuple:
    """Formatta uno step della ricetta"""
    steps = ricetta["steps"]

    if step_num >= len(steps):
        return None, None, "Fine ricetta!"

    step = steps[step_num]

    result = f"📍 **STEP {step_num + 1}/{len(steps)}**\n\n"
    result += f"👨‍🍳 {step['testo']}\n"

    if step.get("timer"):
        minuti = step["timer"] // 60
        secondi = step["timer"] % 60
        if minuti > 0:
            result += f"\n⏱️ Timer: {minuti} minuti"
            if secondi > 0:
                result += f" e {secondi} secondi"
        else:
            result += f"\n⏱️ Timer: {secondi} secondi"

    spoken = f"Step {step_num + 1}. {step['testo']}"

    if step_num < len(steps) - 1:
        result += "\n\n_Dimmi 'avanti' o 'prossimo step' per continuare_"
        spoken += ". Dimmi avanti quando sei pronto."
    else:
        result += "\n\n✅ **Questo era l'ultimo step! Buon appetito!**"
        spoken += " Questo era l'ultimo step. Buon appetito!"

    return result, spoken, step.get("timer")


COOKING_COMPANION_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cooking_companion",
        "description": (
            "烹饪助手 / Assistente cucina hands-free. Guida passo-passo nelle ricette. "
            "Use when: 'cuciniamo', 'come si fa', 'ricetta passo passo', 'guidami', "
            "'prossimo step', 'avanti', 'step successivo', 'ripeti step', 'che ingredienti', "
            "'aiutami a cucinare', 'cucina con me', 'iniziamo a cucinare'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "azione": {
                    "type": "string",
                    "description": "Azione: inizia, avanti, ripeti, ingredienti, stop"
                },
                "ricetta": {
                    "type": "string",
                    "description": "Nome ricetta da cucinare"
                }
            },
            "required": []
        }
    }
}


@register_function('cooking_companion', COOKING_COMPANION_FUNCTION_DESC, ToolType.WAIT)
def cooking_companion(conn, azione: str = None, ricetta: str = None):
    """Assistente cucina passo-passo"""
    global _ricetta_corrente, _step_corrente

    state = load_cooking_state()

    # Ripristina stato
    if state.get("ricetta_corrente") and not _ricetta_corrente:
        _ricetta_corrente = state["ricetta_corrente"]
        _step_corrente = state.get("step", 0)

    azione_lower = (azione or "").lower()

    # === STOP ===
    if any(x in azione_lower for x in ["stop", "basta", "finito", "esci"]):
        _ricetta_corrente = None
        _step_corrente = 0
        state["ricetta_corrente"] = None
        state["step"] = 0
        save_cooking_state(state)

        return ActionResponse(
            action=Action.RESPONSE,
            result="🛑 Sessione cucina terminata!",
            response="Ok, ho interrotto la ricetta. A dopo in cucina!"
        )

    # === AVANTI / PROSSIMO STEP ===
    if any(x in azione_lower for x in ["avanti", "prossimo", "next", "continua", "vai"]):
        if not _ricetta_corrente:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna ricetta in corso!",
                response="Non c'è nessuna ricetta in corso. Dimmi cosa vuoi cucinare!"
            )

        _step_corrente += 1
        state["step"] = _step_corrente
        save_cooking_state(state)

        ricetta_key, ricetta_data = trova_ricetta(_ricetta_corrente)
        if not ricetta_data:
            ricetta_data = RICETTE_GUIDATE.get(_ricetta_corrente)

        if _step_corrente >= len(ricetta_data["steps"]):
            _ricetta_corrente = None
            _step_corrente = 0
            state["ricetta_corrente"] = None
            state["step"] = 0
            save_cooking_state(state)

            return ActionResponse(
                action=Action.RESPONSE,
                result="✅ Ricetta completata! Buon appetito! 🍽️",
                response="Abbiamo finito! La ricetta è completa. Buon appetito!"
            )

        result, spoken, timer = format_step(ricetta_data, _step_corrente)

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    # === RIPETI STEP ===
    if any(x in azione_lower for x in ["ripeti", "ancora", "repeat", "di nuovo", "non ho capito"]):
        if not _ricetta_corrente:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna ricetta in corso!",
                response="Non c'è nessuna ricetta in corso."
            )

        ricetta_key, ricetta_data = trova_ricetta(_ricetta_corrente)
        if not ricetta_data:
            ricetta_data = RICETTE_GUIDATE.get(_ricetta_corrente)

        result, spoken, timer = format_step(ricetta_data, _step_corrente)

        return ActionResponse(
            action=Action.RESPONSE,
            result="🔄 Ripeto:\n\n" + result,
            response="Ripeto. " + spoken
        )

    # === INGREDIENTI ===
    if any(x in azione_lower for x in ["ingredienti", "cosa serve", "cosa mi serve"]):
        if ricetta:
            ricetta_key, ricetta_data = trova_ricetta(ricetta)
        elif _ricetta_corrente:
            ricetta_key, ricetta_data = trova_ricetta(_ricetta_corrente)
            if not ricetta_data:
                ricetta_data = RICETTE_GUIDATE.get(_ricetta_corrente)
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Per quale ricetta vuoi gli ingredienti?",
                response="Per quale ricetta vuoi sapere gli ingredienti?"
            )

        if ricetta_data:
            result = f"🧾 **Ingredienti per {ricetta_data['nome']}** ({ricetta_data['porzioni']} porzioni):\n\n"
            for ing in ricetta_data["ingredienti"]:
                result += f"• {ing}\n"

            spoken = f"Per {ricetta_data['nome']} ti servono: " + ", ".join(ricetta_data["ingredienti"])

            return ActionResponse(
                action=Action.RESPONSE,
                result=result,
                response=spoken
            )

    # === LISTA RICETTE ===
    if not ricetta and not _ricetta_corrente:
        result = "👨‍🍳 **RICETTE DISPONIBILI:**\n\n"
        for key, r in RICETTE_GUIDATE.items():
            result += f"🍳 **{r['nome']}** - {r['tempo_totale']}\n"
        result += "\nDimmi quale vuoi cucinare!"

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response="Ho diverse ricette pronte! Pasta al pomodoro, carbonara, risotto, frittata, caffè con la moka e uova strapazzate. Quale cuciniamo?"
        )

    # === INIZIA RICETTA ===
    if ricetta:
        ricetta_key, ricetta_data = trova_ricetta(ricetta)

        if not ricetta_data:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Non conosco la ricetta '{ricetta}'",
                response=f"Non ho la ricetta per {ricetta} nella mia guida. Prova con pasta, carbonara, risotto, frittata o caffè!"
            )

        _ricetta_corrente = ricetta_key
        _step_corrente = 0
        state["ricetta_corrente"] = ricetta_key
        state["step"] = 0
        save_cooking_state(state)

        # Mostra intro + ingredienti + primo step
        result = f"👨‍🍳 **{ricetta_data['nome']}**\n"
        result += f"⏱️ Tempo: {ricetta_data['tempo_totale']} | 👥 Porzioni: {ricetta_data['porzioni']}\n\n"
        result += "**Ingredienti:**\n"
        for ing in ricetta_data["ingredienti"]:
            result += f"• {ing}\n"
        result += "\n---\n\n"

        step_result, step_spoken, timer = format_step(ricetta_data, 0)
        result += step_result

        spoken = f"Perfetto! Cuciniamo {ricetta_data['nome']}! "
        spoken += f"Ti servono: " + ", ".join(ricetta_data["ingredienti"][:4])
        if len(ricetta_data["ingredienti"]) > 4:
            spoken += f" e altri {len(ricetta_data['ingredienti']) - 4} ingredienti. "
        spoken += f" Iniziamo! {step_spoken}"

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    # Fallback
    return ActionResponse(
        action=Action.RESPONSE,
        result="Cosa vuoi cucinare?",
        response="Dimmi cosa vuoi cucinare e ti guido passo passo!"
    )
