"""
Ginnastica Dolce Plugin - Esercizi guidati vocalmente per anziani
Movimenti semplici e sicuri
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Esercizi organizzati per categoria
ESERCIZI = {
    "riscaldamento": [
        {
            "nome": "Rotazione collo",
            "durata": "30 secondi",
            "istruzioni": [
                "Siediti comodo con la schiena dritta.",
                "Lentamente, inclina la testa verso destra, come per toccare la spalla con l'orecchio.",
                "Mantieni per 5 secondi.",
                "Ora torna al centro.",
                "Inclina verso sinistra.",
                "Mantieni per 5 secondi.",
                "Torna al centro.",
                "Ora ruota lentamente la testa in un cerchio completo.",
                "Prima in senso orario, poi antiorario.",
                "Ottimo lavoro!"
            ]
        },
        {
            "nome": "Rotazione spalle",
            "durata": "30 secondi",
            "istruzioni": [
                "Siediti con le braccia lungo i fianchi.",
                "Solleva le spalle verso le orecchie.",
                "Ruotale all'indietro, facendo un cerchio.",
                "Ripeti 5 volte.",
                "Ora inverti il senso, ruotando in avanti.",
                "Altre 5 volte.",
                "Perfetto!"
            ]
        },
    ],
    "braccia": [
        {
            "nome": "Alzate braccia",
            "durata": "1 minuto",
            "istruzioni": [
                "Siediti con i piedi ben appoggiati a terra.",
                "Le braccia lungo i fianchi.",
                "Lentamente, solleva entrambe le braccia davanti a te.",
                "Continua fino a portarle sopra la testa.",
                "Mantieni per 3 secondi.",
                "Ora abbassa lentamente.",
                "Ripeti 5 volte.",
                "Ricorda di respirare: inspira quando sali, espira quando scendi.",
                "Bravissimo!"
            ]
        },
        {
            "nome": "Apertura braccia",
            "durata": "1 minuto",
            "istruzioni": [
                "Parti con le braccia davanti al petto, palmi uniti.",
                "Lentamente apri le braccia, come per abbracciare qualcuno.",
                "Senti i muscoli del petto che si allungano.",
                "Mantieni per 3 secondi.",
                "Richiudi le braccia al centro.",
                "Ripeti 8 volte.",
                "Benissimo!"
            ]
        },
    ],
    "gambe": [
        {
            "nome": "Marcia da seduti",
            "durata": "1 minuto",
            "istruzioni": [
                "Siediti sulla sedia, schiena dritta.",
                "Solleva il ginocchio destro, come per marciare.",
                "Abbassalo e solleva il sinistro.",
                "Continua alternando, come se stessi camminando.",
                "Vai piano, al tuo ritmo.",
                "Continua per 30 secondi.",
                "Ottimo esercizio per la circolazione!"
            ]
        },
        {
            "nome": "Estensione gambe",
            "durata": "1 minuto",
            "istruzioni": [
                "Siediti con la schiena dritta.",
                "Tieni le mani sui lati della sedia.",
                "Solleva la gamba destra, stendendola davanti a te.",
                "Il piede parallelo al pavimento.",
                "Mantieni per 5 secondi.",
                "Abbassa lentamente.",
                "Ora la gamba sinistra.",
                "Ripeti 5 volte per gamba.",
                "Perfetto!"
            ]
        },
    ],
    "schiena": [
        {
            "nome": "Allungamento schiena",
            "durata": "30 secondi",
            "istruzioni": [
                "Siediti con i piedi ben appoggiati.",
                "Metti le mani sulle ginocchia.",
                "Lentamente, piegati in avanti.",
                "Lascia che la testa penda verso il basso.",
                "Senti la schiena che si allunga.",
                "Mantieni per 10 secondi.",
                "Lentamente torna su, vertebra per vertebra.",
                "Ripeti 3 volte.",
                "Molto bene!"
            ]
        },
    ],
    "mani": [
        {
            "nome": "Esercizio dita",
            "durata": "30 secondi",
            "istruzioni": [
                "Stendi le mani davanti a te.",
                "Apri e chiudi le dita, facendo un pugno.",
                "Ripeti 10 volte.",
                "Ora tocca il pollice con ogni dito, uno alla volta.",
                "Indice, medio, anulare, mignolo.",
                "E torna indietro.",
                "Ottimo per l'artrite!"
            ]
        },
    ],
}

# Sessioni complete
SESSIONI = {
    "breve": ["riscaldamento", "braccia", "mani"],
    "completa": ["riscaldamento", "braccia", "gambe", "schiena", "mani"],
    "mattina": ["riscaldamento", "braccia", "schiena"],
    "sera": ["riscaldamento", "schiena", "mani"],
}

GINNASTICA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "ginnastica_dolce",
        "description": (
            "Esercizi guidati vocalmente per anziani."
            "Usare quando: facciamo ginnastica, esercizi, stretching, muoviamoci, "
            "ginnastica dolce, esercizio per le braccia"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: sessione (completa), singolo (un esercizio), categoria (gruppo)",
                    "enum": ["sessione", "singolo", "categoria"]
                },
                "categoria": {
                    "type": "string",
                    "description": "Categoria: riscaldamento, braccia, gambe, schiena, mani"
                },
                "sessione": {
                    "type": "string",
                    "description": "Sessione: breve (5 min), completa (10 min), mattina, sera"
                }
            },
            "required": [],
        },
    },
}

def format_esercizio(esercizio: dict) -> tuple:
    """Formatta un esercizio per output"""
    nome = esercizio["nome"]
    durata = esercizio["durata"]
    istruzioni = " ".join(esercizio["istruzioni"])

    result = f"**{nome}** ({durata})\n\n{istruzioni}"
    spoken = f"Esercizio: {nome}. Durata: {durata}. " + istruzioni

    return result, spoken

@register_function("ginnastica_dolce", GINNASTICA_FUNCTION_DESC, ToolType.WAIT)
def ginnastica_dolce(conn, tipo: str = "singolo", categoria: str = None, sessione: str = None):
    logger.bind(tag=TAG).info(f"Ginnastica: tipo={tipo}, categoria={categoria}, sessione={sessione}")

    if tipo == "sessione":
        if not sessione or sessione not in SESSIONI:
            opzioni = ", ".join(SESSIONI.keys())
            return ActionResponse(Action.RESPONSE,
                f"Sessioni disponibili: {opzioni}",
                f"Ho sessioni: {opzioni}. Quale preferisci?")

        categorie = SESSIONI[sessione]

        # Costruisci sessione completa
        intro = f"Iniziamo la sessione {sessione}! "
        intro += "Siediti comodo su una sedia stabile. Assicurati di avere spazio intorno a te. "
        intro += "Andremo con calma. Sei pronto? Cominciamo!"

        esercizi_text = [intro]

        for cat in categorie:
            if cat in ESERCIZI:
                es = random.choice(ESERCIZI[cat])
                _, spoken = format_esercizio(es)
                esercizi_text.append(spoken)
                esercizi_text.append("Pausa di 10 secondi... Riprendiamo.")

        esercizi_text.append("Complimenti! Hai completato la sessione. Bravo!")

        full_text = " ".join(esercizi_text)

        return ActionResponse(Action.RESPONSE,
            f"Sessione {sessione} - {len(categorie)} esercizi",
            full_text)

    if tipo == "categoria":
        if not categoria or categoria not in ESERCIZI:
            opzioni = ", ".join(ESERCIZI.keys())
            return ActionResponse(Action.RESPONSE,
                f"Categorie: {opzioni}",
                f"Posso guidarti in esercizi per: {opzioni}. Cosa preferisci?")

        esercizio = random.choice(ESERCIZI[categoria])
        result, spoken = format_esercizio(esercizio)

        intro = f"Esercizio per {categoria}. " + spoken

        return ActionResponse(Action.RESPONSE, result, intro)

    # Singolo esercizio casuale
    if categoria and categoria in ESERCIZI:
        esercizio = random.choice(ESERCIZI[categoria])
    else:
        # Categoria casuale
        cat = random.choice(list(ESERCIZI.keys()))
        esercizio = random.choice(ESERCIZI[cat])

    result, spoken = format_esercizio(esercizio)

    intro = "Ecco un esercizio per te. Siediti comodo. "

    return ActionResponse(Action.RESPONSE, result, intro + spoken)
