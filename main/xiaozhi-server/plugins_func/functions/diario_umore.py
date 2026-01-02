"""
Diario Umore Plugin - Traccia l'umore giornaliero
Con statistiche settimanali
"""

import json
import os
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

UMORE_FILE = "/tmp/xiaozhi_umore.json"

# Emoji e valori umore
UMORI = {
    "felice": {"emoji": "😊", "valore": 5, "alias": ["contento", "allegro", "gioioso", "bene", "benissimo", "ottimo"]},
    "sereno": {"emoji": "🙂", "valore": 4, "alias": ["tranquillo", "calmo", "rilassato", "ok", "normale"]},
    "neutro": {"emoji": "😐", "valore": 3, "alias": ["così così", "insomma", "medio", "nè bene nè male"]},
    "triste": {"emoji": "😢", "valore": 2, "alias": ["giù", "malinconico", "abbattuto", "male"]},
    "arrabbiato": {"emoji": "😠", "valore": 1, "alias": ["nervoso", "irritato", "frustrato", "stressato"]},
}

def load_umore() -> dict:
    try:
        if os.path.exists(UMORE_FILE):
            with open(UMORE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"registrazioni": []}

def save_umore(data: dict):
    try:
        with open(UMORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio umore: {e}")

def parse_umore(testo: str) -> tuple:
    """Identifica l'umore dal testo"""
    testo = testo.lower().strip()

    for umore, info in UMORI.items():
        if umore in testo:
            return umore, info
        for alias in info["alias"]:
            if alias in testo:
                return umore, info

    return None, None

UMORE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "diario_umore",
        "description": (
            "Traccia l'umore giornaliero con statistiche."
            "Usare quando: come mi sento oggi, registra il mio umore, sono felice, "
            "sono triste, diario umore, statistiche umore"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: register (registra umore), stats (statistiche), history (storico)",
                    "enum": ["register", "stats", "history"]
                },
                "umore": {
                    "type": "string",
                    "description": "Stato d'animo (felice, sereno, neutro, triste, arrabbiato)"
                },
                "nota": {
                    "type": "string",
                    "description": "Nota opzionale sul perché"
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("diario_umore", UMORE_FUNCTION_DESC, ToolType.WAIT)
def diario_umore(conn, action: str = "register", umore: str = None, nota: str = None):
    logger.bind(tag=TAG).info(f"Umore: action={action}, umore={umore}")

    data = load_umore()
    registrazioni = data.get("registrazioni", [])

    if action == "register":
        if not umore:
            opzioni = ", ".join(UMORI.keys())
            return ActionResponse(Action.RESPONSE,
                f"Come ti senti? ({opzioni})",
                "Come ti senti oggi? Puoi dirmi felice, sereno, neutro, triste o arrabbiato")

        umore_key, umore_info = parse_umore(umore)

        if not umore_key:
            opzioni = ", ".join(UMORI.keys())
            return ActionResponse(Action.RESPONSE,
                f"Non ho capito. Opzioni: {opzioni}",
                f"Non ho capito il tuo umore. Puoi scegliere tra: {opzioni}")

        oggi = datetime.now().strftime("%Y-%m-%d")
        ora = datetime.now().strftime("%H:%M")

        # Rimuovi registrazione precedente di oggi se esiste
        registrazioni = [r for r in registrazioni if r.get("data") != oggi]

        registrazioni.append({
            "data": oggi,
            "ora": ora,
            "umore": umore_key,
            "valore": umore_info["valore"],
            "nota": nota or ""
        })

        data["registrazioni"] = registrazioni
        save_umore(data)

        emoji = umore_info["emoji"]
        nota_str = f" Nota: {nota}." if nota else ""

        risposte_positive = [
            f"Ho registrato che oggi ti senti {umore_key} {emoji}.{nota_str}",
            f"Capito, oggi umore {umore_key} {emoji}.{nota_str}",
        ]

        import random
        risposta = random.choice(risposte_positive)

        if umore_info["valore"] >= 4:
            risposta += " Che bello!"
        elif umore_info["valore"] <= 2:
            risposta += " Spero che domani vada meglio."

        return ActionResponse(Action.RESPONSE, risposta, risposta)

    if action == "stats":
        if not registrazioni:
            return ActionResponse(Action.RESPONSE,
                "Nessuna registrazione",
                "Non hai ancora registrato il tuo umore. Dimmi come ti senti oggi!")

        # Ultimi 7 giorni
        oggi = datetime.now()
        settimana_fa = (oggi - timedelta(days=7)).strftime("%Y-%m-%d")

        recenti = [r for r in registrazioni if r["data"] >= settimana_fa]

        if not recenti:
            return ActionResponse(Action.RESPONSE,
                "Nessun dato questa settimana",
                "Non hai registrazioni negli ultimi 7 giorni")

        # Calcola media
        media = sum(r["valore"] for r in recenti) / len(recenti)

        # Conta umori
        conteggio = {}
        for r in recenti:
            u = r["umore"]
            conteggio[u] = conteggio.get(u, 0) + 1

        # Umore più frequente
        piu_frequente = max(conteggio, key=conteggio.get)

        # Descrizione media
        if media >= 4.5:
            desc_media = "ottima"
        elif media >= 3.5:
            desc_media = "buona"
        elif media >= 2.5:
            desc_media = "nella media"
        else:
            desc_media = "sotto la media"

        result = f"Statistiche ultimi 7 giorni:\n"
        result += f"- Registrazioni: {len(recenti)}\n"
        result += f"- Media: {media:.1f}/5 ({desc_media})\n"
        result += f"- Umore più frequente: {piu_frequente}\n"

        spoken = f"Negli ultimi 7 giorni hai {len(recenti)} registrazioni. "
        spoken += f"La tua media è {desc_media}, con {piu_frequente} come umore più frequente."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "history":
        if not registrazioni:
            return ActionResponse(Action.RESPONSE,
                "Nessuna registrazione",
                "Non hai ancora registrato il tuo umore")

        # Ultime 7 registrazioni
        ultime = sorted(registrazioni, key=lambda x: x["data"], reverse=True)[:7]

        result = "Ultime registrazioni:\n"
        spoken = "Le tue ultime registrazioni: "

        for r in ultime:
            emoji = UMORI.get(r["umore"], {}).get("emoji", "")
            result += f"- {r['data']}: {r['umore']} {emoji}\n"
            spoken += f"{r['data']}, {r['umore']}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    return ActionResponse(Action.RESPONSE,
        "Vuoi registrare il tuo umore?",
        "Vuoi dirmi come ti senti oggi?")
