"""
Diario Vocale - Registra pensieri e riflessioni quotidiane
Analizza umore e crea storico
"""

from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.user_memory import get_user_memory

TAG = __name__
logger = setup_logging()

# Domande guida per il diario
DOMANDE_DIARIO = [
    "Come ti sei sentito oggi?",
    "Qual è stata la cosa più bella della giornata?",
    "C'è qualcosa che ti ha dato fastidio?",
    "Cosa hai imparato oggi?",
    "Per cosa sei grato oggi?",
    "Come descriveresti la tua giornata in una parola?",
]

# Parole chiave per analisi umore
PAROLE_POSITIVE = ["bene", "felice", "contento", "sereno", "tranquillo", "allegro",
                   "soddisfatto", "grato", "fortunato", "entusiasta", "rilassato"]
PAROLE_NEGATIVE = ["male", "triste", "arrabbiato", "stanco", "stressato", "ansioso",
                   "preoccupato", "deluso", "frustrato", "solo", "sola"]


def analizza_umore_testo(testo: str) -> str:
    """Analizza l'umore dal testo"""
    testo_lower = testo.lower()

    positivi = sum(1 for p in PAROLE_POSITIVE if p in testo_lower)
    negativi = sum(1 for p in PAROLE_NEGATIVE if p in testo_lower)

    if positivi > negativi:
        return "positivo"
    elif negativi > positivi:
        return "negativo"
    return "neutro"


def get_emoji_umore(umore: str) -> str:
    """Restituisce emoji per l'umore"""
    return {
        "positivo": "😊",
        "negativo": "😔",
        "neutro": "😐"
    }.get(umore, "📝")


DIARIO_VOCALE_DESC = {
    "type": "function",
    "function": {
        "name": "diario_vocale",
        "description": (
            "Diario vocale per registrare pensieri e riflessioni. "
            "Usare per: scrivi sul diario, diario, voglio scrivere, "
            "registra pensiero, nota vocale diario, come mi sento oggi, "
            "riflessione, annotazione, oggi è successo"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "contenuto": {
                    "type": "string",
                    "description": "Contenuto da registrare nel diario"
                },
                "azione": {
                    "type": "string",
                    "description": "Azione da eseguire",
                    "enum": ["scrivi", "leggi", "riassunto"]
                }
            },
            "required": []
        }
    }
}


@register_function('diario_vocale', DIARIO_VOCALE_DESC, ToolType.WAIT)
def diario_vocale(conn, contenuto: str = None, azione: str = "scrivi"):
    """Gestisce il diario vocale dell'utente"""

    device_id = getattr(conn, 'device_id', 'unknown')
    logger.bind(tag=TAG).info(f"Diario vocale per {device_id}: {azione}")

    memoria = get_user_memory(device_id)
    nome = memoria.data.get("nome_utente") or "amico"

    # Inizializza diario se non esiste
    if "diario" not in memoria.data:
        memoria.data["diario"] = []

    if azione == "leggi":
        # Leggi ultime voci
        diario = memoria.data.get("diario", [])
        if not diario:
            parlato = f"{nome}, il tuo diario è ancora vuoto. Vuoi raccontarmi qualcosa?"
            display = "📔 **Il tuo diario è vuoto**\n\nDimmi qualcosa e lo annoterò per te!"
        else:
            ultime = diario[-3:]  # Ultime 3 voci
            parlato = f"Ecco le ultime annotazioni del tuo diario, {nome}. "

            display = f"📔 **Il tuo Diario**\n\n"
            for voce in ultime:
                data = voce.get("data", "")
                testo = voce.get("testo", "")
                umore = voce.get("umore", "neutro")
                emoji = get_emoji_umore(umore)

                display += f"{emoji} **{data}**\n{testo}\n\n"
                parlato += f"Il {data}: {testo[:100]}. "

    elif azione == "riassunto":
        # Riassunto statistiche diario
        diario = memoria.data.get("diario", [])
        totale = len(diario)

        if totale == 0:
            parlato = "Non hai ancora scritto nulla sul diario."
            display = "📔 **Diario vuoto**"
        else:
            positivi = sum(1 for v in diario if v.get("umore") == "positivo")
            negativi = sum(1 for v in diario if v.get("umore") == "negativo")
            neutri = totale - positivi - negativi

            parlato = f"{nome}, hai scritto {totale} voci nel diario. "
            parlato += f"{positivi} giorni positivi, {negativi} difficili, {neutri} nella media."

            display = f"📊 **Statistiche Diario**\n\n"
            display += f"📝 Voci totali: {totale}\n"
            display += f"😊 Giorni positivi: {positivi}\n"
            display += f"😔 Giorni difficili: {negativi}\n"
            display += f"😐 Giorni neutri: {neutri}"

    else:  # scrivi
        if not contenuto:
            # Chiedi cosa scrivere
            import random
            domanda = random.choice(DOMANDE_DIARIO)
            parlato = f"{nome}, {domanda}"
            display = f"📔 **Diario Vocale**\n\n{domanda}\n\nRaccontami, ti ascolto."
        else:
            # Salva nel diario
            oggi = datetime.now()
            umore = analizza_umore_testo(contenuto)

            voce = {
                "data": oggi.strftime("%d/%m/%Y %H:%M"),
                "testo": contenuto[:500],  # Limita lunghezza
                "umore": umore
            }

            memoria.data["diario"].append(voce)
            memoria.data["diario"] = memoria.data["diario"][-100:]  # Max 100 voci
            memoria._save()

            emoji = get_emoji_umore(umore)
            parlato = f"Ho annotato nel tuo diario, {nome}. "
            if umore == "positivo":
                parlato += "Sembra una giornata positiva!"
            elif umore == "negativo":
                parlato += "Capisco, a volte le giornate sono difficili. Sono qui per te."
            else:
                parlato += "Grazie per aver condiviso."

            display = f"📔 **Annotato nel diario** {emoji}\n\n"
            display += f"📅 {oggi.strftime('%d/%m/%Y %H:%M')}\n\n"
            display += f"*\"{contenuto[:200]}{'...' if len(contenuto) > 200 else ''}\"*"

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
