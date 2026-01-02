"""
Dado Plugin - Lancia dadi virtuali
Per giochi da tavolo e decisioni casuali
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Facce dei dadi per visualizzazione
DADO_FACCE = {
    1: "⚀",
    2: "⚁",
    3: "⚂",
    4: "⚃",
    5: "⚄",
    6: "⚅",
}

DADO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "dado",
        "description": (
            "Lancia dadi virtuali o moneta."
            "Usare quando: lancia un dado, tira i dadi, dado, D6, D20, "
            "testa o croce, lancio moneta, numero casuale"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: dado (D6), d20, moneta, dado_N (N facce), NumDNum (es: 2d6)",
                },
                "quantita": {
                    "type": "integer",
                    "description": "Numero di dadi da lanciare (default 1)"
                }
            },
            "required": [],
        },
    },
}

def parse_dado(tipo: str) -> tuple:
    """Parsa il tipo di dado e restituisce (quantità, facce)"""
    if not tipo:
        return 1, 6

    tipo = tipo.lower().strip()

    # Formato NdF (es: 2d6, 3d20)
    if "d" in tipo and tipo[0].isdigit():
        parts = tipo.split("d")
        try:
            quantita = int(parts[0]) if parts[0] else 1
            facce = int(parts[1])
            return min(quantita, 10), min(facce, 100)  # Limiti ragionevoli
        except:
            pass

    # Formato dN (es: d6, d20)
    if tipo.startswith("d") and tipo[1:].isdigit():
        try:
            facce = int(tipo[1:])
            return 1, min(facce, 100)
        except:
            pass

    # Moneta
    if tipo in ["moneta", "coin", "testa", "croce", "flip"]:
        return 1, 2

    # Default: d6
    return 1, 6

def numero_a_parole(n: int) -> str:
    """Converte numero in parole"""
    numeri = ["zero", "uno", "due", "tre", "quattro", "cinque",
              "sei", "sette", "otto", "nove", "dieci",
              "undici", "dodici", "tredici", "quattordici", "quindici",
              "sedici", "diciassette", "diciotto", "diciannove", "venti"]
    if n < len(numeri):
        return numeri[n]
    return str(n)

@register_function("dado", DADO_FUNCTION_DESC, ToolType.WAIT)
def dado(conn, tipo: str = None, quantita: int = None):
    logger.bind(tag=TAG).info(f"Dado: tipo={tipo}, quantita={quantita}")

    q, facce = parse_dado(tipo)

    # Se specificata quantità esplicitamente
    if quantita:
        q = min(quantita, 10)

    # Caso speciale: moneta
    if facce == 2:
        risultato = random.choice(["Testa", "Croce"])
        emoji = "🪙"

        result = f"{emoji} **LANCIO MONETA**\n\n"
        result += f"➡️ **{risultato}!**"

        spoken = f"Lancio la moneta... {risultato}!"

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Lancia i dadi
    risultati = [random.randint(1, facce) for _ in range(q)]
    totale = sum(risultati)

    # Formatta output
    if facce == 6 and q <= 5:
        # Usa emoji per d6
        dadi_visual = " ".join([DADO_FACCE.get(r, str(r)) for r in risultati])
    else:
        dadi_visual = " + ".join(map(str, risultati))

    result = f"🎲 **LANCIO {'DADO' if q == 1 else 'DADI'}** ({q}d{facce})\n\n"
    result += f"➡️ {dadi_visual}\n\n"

    if q > 1:
        result += f"**Totale: {totale}**"

    # Spoken
    if q == 1:
        spoken = f"Lancio il dado a {facce} facce... {numero_a_parole(risultati[0])}!"
    else:
        risultati_parlati = ", ".join([numero_a_parole(r) for r in risultati])
        spoken = f"Lancio {q} dadi... {risultati_parlati}. Totale: {totale}!"

    # Commenti speciali
    if facce == 6:
        if risultati[0] == 6:
            spoken += " Numero massimo!"
        elif risultati[0] == 1:
            spoken += " Ops, il minimo!"

    if facce == 20 and risultati[0] == 20:
        result += "\n\n🎉 **CRITICO!**"
        spoken += " Critico! Venti naturale!"
    elif facce == 20 and risultati[0] == 1:
        result += "\n\n💀 **FALLIMENTO CRITICO!**"
        spoken += " Fallimento critico!"

    return ActionResponse(Action.RESPONSE, result, spoken)
