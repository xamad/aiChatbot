"""
Oroscopo Plugin - Oroscopo giornaliero per segno zodiacale
Previsioni generate dinamicamente
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Dati segni zodiacali
SEGNI = {
    "ariete": {"emoji": "♈", "elemento": "fuoco", "date": "21 marzo - 19 aprile"},
    "toro": {"emoji": "♉", "elemento": "terra", "date": "20 aprile - 20 maggio"},
    "gemelli": {"emoji": "♊", "elemento": "aria", "date": "21 maggio - 20 giugno"},
    "cancro": {"emoji": "♋", "elemento": "acqua", "date": "21 giugno - 22 luglio"},
    "leone": {"emoji": "♌", "elemento": "fuoco", "date": "23 luglio - 22 agosto"},
    "vergine": {"emoji": "♍", "elemento": "terra", "date": "23 agosto - 22 settembre"},
    "bilancia": {"emoji": "♎", "elemento": "aria", "date": "23 settembre - 22 ottobre"},
    "scorpione": {"emoji": "♏", "elemento": "acqua", "date": "23 ottobre - 21 novembre"},
    "sagittario": {"emoji": "♐", "elemento": "fuoco", "date": "22 novembre - 21 dicembre"},
    "capricorno": {"emoji": "♑", "elemento": "terra", "date": "22 dicembre - 19 gennaio"},
    "acquario": {"emoji": "♒", "elemento": "aria", "date": "20 gennaio - 18 febbraio"},
    "pesci": {"emoji": "♓", "elemento": "acqua", "date": "19 febbraio - 20 marzo"},
}

# Frasi per generare oroscopo
FRASI_AMORE = [
    "In amore, le stelle ti sorridono oggi. Un incontro speciale potrebbe sorprenderti.",
    "La vita sentimentale richiede pazienza. Non forzare le situazioni.",
    "Venere ti è favorevole! Ottimo momento per dichiarazioni romantiche.",
    "Qualche tensione in coppia, ma nulla che non si possa risolvere con il dialogo.",
    "Single? Oggi potresti fare un incontro interessante.",
    "L'armonia regna nel tuo cuore. Condividi questa gioia con chi ami.",
    "Un pizzico di gelosia potrebbe complicare le cose. Mantieni la calma.",
    "L'amore è nell'aria! Apriti a nuove possibilità.",
]

FRASI_LAVORO = [
    "Sul lavoro, nuove opportunità si profilano all'orizzonte.",
    "Un progetto importante potrebbe finalmente decollare.",
    "Attenzione ai colleghi: non tutti hanno le tue stesse intenzioni.",
    "La tua creatività sarà molto apprezzata oggi.",
    "Giornata impegnativa ma produttiva. I risultati arriveranno.",
    "Un superiore noterà i tuoi sforzi. Continua così!",
    "Evita decisioni affrettate in ambito professionale.",
    "Ottimo momento per chiedere un aumento o una promozione.",
]

FRASI_SALUTE = [
    "Energia alle stelle! Approfitta per fare attività fisica.",
    "Un po' di stanchezza potrebbe farsi sentire. Riposa di più.",
    "Ottima forma fisica e mentale. Tutto procede bene.",
    "Non trascurare l'alimentazione: mangia sano!",
    "Lo stress potrebbe giocarti brutti scherzi. Relax!",
    "Giornata ideale per iniziare una nuova routine salutare.",
    "Qualche piccolo malessere, nulla di grave. Riguardati.",
    "Pieno di vitalità! Le energie non ti mancano.",
]

FRASI_FORTUNA = [
    "Fortuna dalla tua parte! I numeri fortunati sono",
    "Le stelle consigliano prudenza con il denaro.",
    "Giornata fortunata per piccoli colpi di fortuna.",
    "Evita spese superflue, non è il momento giusto.",
    "Una piacevole sorpresa potrebbe arrivare.",
    "La fortuna aiuta gli audaci: osa un po' di più!",
    "Giornata neutra per la fortuna. Aspetta momenti migliori.",
    "Le stelle ti proteggono. Tutto andrà bene.",
]

OROSCOPO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "oroscopo",
        "description": (
            "Fornisce l'oroscopo giornaliero per segno zodiacale."
            "Usare quando: oroscopo ariete, che dice l'oroscopo, previsioni per toro, "
            "cosa dicono le stelle, segno zodiacale, stelle"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "segno": {
                    "type": "string",
                    "description": "Segno zodiacale"
                },
                "area": {
                    "type": "string",
                    "description": "Area specifica: amore, lavoro, salute, fortuna, tutto",
                    "enum": ["amore", "lavoro", "salute", "fortuna", "tutto"]
                }
            },
            "required": [],
        },
    },
}

def trova_segno(query: str) -> str:
    """Trova il segno zodiacale dalla query"""
    query = query.lower().strip()

    for segno in SEGNI.keys():
        if segno in query:
            return segno

    return None

def genera_oroscopo(segno: str, area: str = "tutto") -> tuple:
    """Genera oroscopo per segno e area"""
    info = SEGNI[segno]

    # Seed basato su data e segno per consistenza giornaliera
    oggi = datetime.now().strftime("%Y%m%d")
    seed = hash(f"{oggi}{segno}")
    random.seed(seed)

    # Numeri fortunati
    numeri = sorted(random.sample(range(1, 91), 3))
    numeri_str = ", ".join(map(str, numeri))

    # Valutazione generale (1-5 stelle)
    stelle = random.randint(2, 5)
    stelle_visual = "⭐" * stelle

    if area == "tutto":
        amore = random.choice(FRASI_AMORE)
        lavoro = random.choice(FRASI_LAVORO)
        salute = random.choice(FRASI_SALUTE)
        fortuna = random.choice(FRASI_FORTUNA)

        result = f"{info['emoji']} **{segno.upper()}** - {stelle_visual}\n\n"
        result += f"💕 **Amore**: {amore}\n\n"
        result += f"💼 **Lavoro**: {lavoro}\n\n"
        result += f"🏥 **Salute**: {salute}\n\n"
        result += f"🍀 **Fortuna**: {fortuna} {numeri_str}."

        spoken = f"Oroscopo {segno}. "
        spoken += f"Amore: {amore} "
        spoken += f"Lavoro: {lavoro} "
        spoken += f"Salute: {salute} "
        spoken += f"Numeri fortunati: {numeri_str}."
    else:
        if area == "amore":
            frase = random.choice(FRASI_AMORE)
            emoji = "💕"
        elif area == "lavoro":
            frase = random.choice(FRASI_LAVORO)
            emoji = "💼"
        elif area == "salute":
            frase = random.choice(FRASI_SALUTE)
            emoji = "🏥"
        else:  # fortuna
            frase = random.choice(FRASI_FORTUNA)
            emoji = "🍀"

        result = f"{info['emoji']} **{segno.upper()}** - {area.capitalize()}\n\n"
        result += f"{emoji} {frase}"

        if area == "fortuna":
            result += f" {numeri_str}."

        spoken = f"Oroscopo {segno}, {area}. {frase}"

    # Reset random seed
    random.seed()

    return result, spoken

@register_function("oroscopo", OROSCOPO_FUNCTION_DESC, ToolType.WAIT)
def oroscopo(conn, segno: str = None, area: str = "tutto"):
    logger.bind(tag=TAG).info(f"Oroscopo: segno={segno}, area={area}")

    if not segno:
        segni_lista = ", ".join([f"{info['emoji']} {s.capitalize()}" for s, info in list(SEGNI.items())[:6]])
        return ActionResponse(Action.RESPONSE,
            f"Di quale segno vuoi l'oroscopo?\n\n{segni_lista}...",
            "Di quale segno zodiacale vuoi l'oroscopo?")

    segno_trovato = trova_segno(segno)

    if not segno_trovato:
        return ActionResponse(Action.RESPONSE,
            f"Non conosco il segno '{segno}'. Prova con ariete, toro, gemelli...",
            f"Non ho capito il segno. Dimmi ariete, toro, gemelli o un altro segno zodiacale.")

    result, spoken = genera_oroscopo(segno_trovato, area)

    return ActionResponse(Action.RESPONSE, result, spoken)
