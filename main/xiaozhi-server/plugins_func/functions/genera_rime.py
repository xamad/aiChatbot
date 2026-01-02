"""
Genera Rime Plugin - Trova rime per parole
Per poesie, canzoni e giochi
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Database rime comuni italiane (organizzato per desinenza)
RIME = {
    # -ore
    "ore": ["amore", "cuore", "dolore", "fiore", "colore", "calore", "sapore", "valore", "errore", "signore", "onore", "rumore", "umore", "timore", "pudore"],
    # -ato
    "ato": ["amato", "passato", "stato", "nato", "parlato", "mangiato", "pensato", "trovato", "lasciato", "formato", "creato", "dato", "mandato", "guardato"],
    # -ino
    "ino": ["bambino", "mattino", "cammino", "destino", "vicino", "carino", "piccino", "divino", "vino", "pino", "postino", "giardino", "cugino", "latino"],
    # -ello
    "ello": ["bello", "fratello", "castello", "cappello", "cervello", "uccello", "gioiello", "modello", "martello", "anello", "ombrello", "coltello"],
    # -ente
    "ente": ["gente", "mente", "presente", "niente", "sempre", "dolcemente", "certamente", "solamente", "lentamente", "fortemente", "velocemente"],
    # -ano
    "ano": ["mano", "piano", "lontano", "umano", "strano", "sano", "romano", "italiano", "americano", "cristiano", "anziano", "villano"],
    # -are
    "are": ["amare", "parlare", "giocare", "cantare", "ballare", "mangiare", "sognare", "volare", "pensare", "trovare", "chiamare", "guardare"],
    # -ero
    "ero": ["vero", "nero", "intero", "pensiero", "sincero", "severo", "straniero", "cavaliero", "guerriero", "sentiero", "mistero", "impero"],
    # -ita
    "ita": ["vita", "infinita", "finita", "unita", "partita", "ferita", "salita", "uscita", "visita", "gradita"],
    # -one
    "one": ["azione", "passione", "canzone", "ragione", "stagione", "emozione", "occasione", "lezione", "nazione", "visione", "decisione"],
    # -ia
    "ia": ["via", "mia", "sia", "magia", "poesia", "fantasia", "armonia", "allegria", "malinconia", "simpatia", "pazzia", "follia"],
    # -ezza
    "ezza": ["bellezza", "dolcezza", "tristezza", "certezza", "tenerezza", "grandezza", "debolezza", "sicurezza", "carezza", "giovinezza"],
    # -ura
    "ura": ["natura", "cultura", "paura", "avventura", "figura", "cura", "misura", "temperatura", "struttura", "pittura", "lettura"],
    # -ento
    "ento": ["momento", "vento", "sentimento", "pensamento", "lento", "contento", "spento", "accento", "evento", "movimento", "tempo"],
    # -anno
    "anno": ["anno", "fanno", "vanno", "sanno", "stanno", "affanno", "inganno", "danno", "panno", "capodanno"],
    # -ata
    "ata": ["giornata", "serata", "mattinata", "passeggiata", "chiamata", "volta", "strada", "cascata", "entrata", "uscita"],
    # -etta
    "etta": ["fretta", "casetta", "bicicletta", "paletta", "sigaretta", "festa", "forchetta", "vendetta", "civetta", "staffetta"],
}

RIME_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "genera_rime",
        "description": (
            "Trova rime per una parola. Usa quando l'utente dice: "
            "'trova rime per amore', 'cosa rima con cuore?', 'rime per...', "
            "'parole che rimano', 'aiutami con una poesia'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "parola": {
                    "type": "string",
                    "description": "Parola per cui trovare rime"
                }
            },
            "required": ["parola"],
        },
    },
}

def trova_desinenza(parola: str) -> str:
    """Trova la desinenza più lunga che matcha"""
    parola = parola.lower().strip()

    # Prova desinenze dalla più lunga alla più corta
    for lunghezza in range(min(5, len(parola)), 1, -1):
        desinenza = parola[-lunghezza:]
        if desinenza in RIME:
            return desinenza

    # Prova le ultime 2-3 lettere
    if len(parola) >= 3:
        return parola[-3:]
    return parola[-2:]

def trova_rime(parola: str) -> list:
    """Trova rime per una parola"""
    parola = parola.lower().strip()
    desinenza = trova_desinenza(parola)

    # Cerca nel database
    if desinenza in RIME:
        rime = [r for r in RIME[desinenza] if r.lower() != parola]
        return rime

    # Cerca parole con desinenza simile
    risultati = []
    for des, rime_list in RIME.items():
        for rima in rime_list:
            if rima.endswith(parola[-2:]) and rima.lower() != parola:
                risultati.append(rima)

    return list(set(risultati))[:10]

@register_function("genera_rime", RIME_FUNCTION_DESC, ToolType.WAIT)
def genera_rime(conn, parola: str = None):
    logger.bind(tag=TAG).info(f"Rime: parola={parola}")

    if not parola:
        return ActionResponse(Action.RESPONSE,
            "📝 Per quale parola vuoi le rime?",
            "Dimmi una parola e ti troverò delle rime")

    rime = trova_rime(parola)

    if not rime:
        # Suggerisci basandosi sulla desinenza
        desinenza = trova_desinenza(parola)
        return ActionResponse(Action.RESPONSE,
            f"Non ho rime esatte per '{parola}' (desinenza: -{desinenza})",
            f"Non ho trovato rime per {parola}. Prova con un'altra parola.")

    # Limita a 8 rime
    rime = rime[:8]

    result = f"📝 **RIME PER '{parola.upper()}'**\n\n"
    result += "\n".join([f"• {r}" for r in rime])

    spoken = f"Ecco le rime per {parola}: " + ", ".join(rime[:5])

    # Suggerisci un verso
    if len(rime) >= 2:
        rima1 = random.choice(rime)
        result += f"\n\n💡 _Esempio: \"{parola}\" rima con \"{rima1}\"_"

    return ActionResponse(Action.RESPONSE, result, spoken)
