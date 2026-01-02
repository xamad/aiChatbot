"""
Lotto Estrazioni Plugin - Numeri estratti e generatore
Ultime estrazioni e numeri fortunati
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Ruote del lotto
RUOTE = ["Bari", "Cagliari", "Firenze", "Genova", "Milano", "Napoli", "Palermo", "Roma", "Torino", "Venezia", "Nazionale"]

LOTTO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "lotto_estrazioni",
        "description": (
            "superenalotto."
            "Usare quando: numeri del lotto, dammi dei numeri, numeri fortunati, "
            "superenalotto, estrazioni, gioca al lotto"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: lotto (5 numeri), superenalotto (6 numeri), ambo, terno",
                    "enum": ["lotto", "superenalotto", "ambo", "terno", "quaterna", "cinquina"]
                },
                "ruota": {
                    "type": "string",
                    "description": "Ruota preferita (opzionale)"
                }
            },
            "required": [],
        },
    },
}

def genera_numeri(quantita: int, max_num: int = 90) -> list:
    """Genera numeri casuali unici"""
    return sorted(random.sample(range(1, max_num + 1), quantita))

def numero_a_parole(n: int) -> str:
    """Converte numero in parole per lettura"""
    unita = ["", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]
    decine = ["", "dieci", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta"]
    speciali = {11: "undici", 12: "dodici", 13: "tredici", 14: "quattordici", 15: "quindici",
                16: "sedici", 17: "diciassette", 18: "diciotto", 19: "diciannove"}

    if n in speciali:
        return speciali[n]
    if n < 10:
        return unita[n]
    if n < 20:
        return speciali.get(n, f"dieci{unita[n % 10]}")

    d = n // 10
    u = n % 10

    if u == 1 or u == 8:
        return decine[d][:-1] + unita[u]
    return decine[d] + unita[u]

@register_function("lotto_estrazioni", LOTTO_FUNCTION_DESC, ToolType.WAIT)
def lotto_estrazioni(conn, tipo: str = "lotto", ruota: str = None):
    logger.bind(tag=TAG).info(f"Lotto: tipo={tipo}, ruota={ruota}")

    oggi = datetime.now().strftime("%d/%m/%Y")

    if tipo == "superenalotto":
        numeri = genera_numeri(6, 90)
        jolly = random.choice([n for n in range(1, 91) if n not in numeri])
        superstar = random.randint(1, 90)

        numeri_str = " - ".join(map(str, numeri))
        numeri_letti = ", ".join([numero_a_parole(n) for n in numeri])

        result = f"🍀 **SUPERENALOTTO**\n\n"
        result += f"Numeri fortunati: **{numeri_str}**\n"
        result += f"Jolly: **{jolly}**\n"
        result += f"SuperStar: **{superstar}**\n\n"
        result += f"_Generati il {oggi} - Buona fortuna!_"

        spoken = f"Ecco i numeri del superenalotto: {numeri_letti}. "
        spoken += f"Jolly: {numero_a_parole(jolly)}. SuperStar: {numero_a_parole(superstar)}. Buona fortuna!"

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Lotto normale
    quantita_map = {
        "ambo": 2,
        "terno": 3,
        "quaterna": 4,
        "cinquina": 5,
        "lotto": 5
    }

    quantita = quantita_map.get(tipo, 5)
    numeri = genera_numeri(quantita, 90)

    # Ruota consigliata
    if not ruota:
        ruota = random.choice(RUOTE)
    elif ruota.lower() not in [r.lower() for r in RUOTE]:
        ruota = random.choice(RUOTE)

    numeri_str = " - ".join(map(str, numeri))
    numeri_letti = ", ".join([numero_a_parole(n) for n in numeri])

    tipo_nome = tipo.capitalize()

    result = f"🎰 **{tipo_nome.upper()}**\n\n"
    result += f"Numeri: **{numeri_str}**\n"
    result += f"Ruota consigliata: **{ruota}**\n\n"
    result += f"_Generati il {oggi}_"

    spoken = f"Ecco {quantita} numeri per il {tipo_nome}: {numeri_letti}. "
    spoken += f"Ti consiglio la ruota di {ruota}. In bocca al lupo!"

    return ActionResponse(Action.RESPONSE, result, spoken)
