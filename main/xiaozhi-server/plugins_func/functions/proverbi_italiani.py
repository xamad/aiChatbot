"""
Proverbi Italiani Plugin - Saggezza popolare italiana
Proverbi con spiegazione
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

PROVERBI = [
    {
        "proverbio": "Chi va piano va sano e va lontano",
        "significato": "Agire con calma e prudenza porta a risultati migliori e duraturi",
        "uso": "Per consigliare pazienza e prudenza"
    },
    {
        "proverbio": "Chi dorme non piglia pesci",
        "significato": "Bisogna essere attivi e laboriosi per ottenere risultati",
        "uso": "Per spronare qualcuno all'azione"
    },
    {
        "proverbio": "Il mattino ha l'oro in bocca",
        "significato": "Le prime ore del giorno sono le più produttive",
        "uso": "Per esortare a svegliarsi presto"
    },
    {
        "proverbio": "L'erba del vicino è sempre più verde",
        "significato": "Tendiamo a desiderare ciò che hanno gli altri",
        "uso": "Per far riflettere sull'invidia"
    },
    {
        "proverbio": "Non è tutto oro quel che luccica",
        "significato": "Le apparenze ingannano, bisogna guardare oltre la superficie",
        "uso": "Per avvertire di non fidarsi delle apparenze"
    },
    {
        "proverbio": "Chi trova un amico trova un tesoro",
        "significato": "La vera amicizia è un bene prezioso",
        "uso": "Per sottolineare il valore dell'amicizia"
    },
    {
        "proverbio": "Una mela al giorno toglie il medico di torno",
        "significato": "Una buona alimentazione aiuta a mantenersi in salute",
        "uso": "Per consigliare uno stile di vita sano"
    },
    {
        "proverbio": "Meglio tardi che mai",
        "significato": "È sempre meglio fare qualcosa in ritardo che non farla affatto",
        "uso": "Per consolare chi è in ritardo"
    },
    {
        "proverbio": "Ride bene chi ride ultimo",
        "significato": "La vittoria finale è quella che conta",
        "uso": "Per incoraggiare chi sta perdendo"
    },
    {
        "proverbio": "A caval donato non si guarda in bocca",
        "significato": "Un regalo va accettato senza criticare",
        "uso": "Per ricordare la gratitudine"
    },
    {
        "proverbio": "Chi la fa l'aspetti",
        "significato": "Le azioni negative prima o poi tornano indietro",
        "uso": "Come avvertimento"
    },
    {
        "proverbio": "Tra il dire e il fare c'è di mezzo il mare",
        "significato": "È facile parlare, difficile agire",
        "uso": "Per sottolineare che le azioni contano più delle parole"
    },
    {
        "proverbio": "Chi non risica non rosica",
        "significato": "Senza correre rischi non si ottiene nulla",
        "uso": "Per incoraggiare a osare"
    },
    {
        "proverbio": "L'appetito vien mangiando",
        "significato": "Iniziando un'attività, cresce la voglia di continuare",
        "uso": "Per incoraggiare a iniziare"
    },
    {
        "proverbio": "Chi ben comincia è a metà dell'opera",
        "significato": "Un buon inizio facilita tutto il lavoro",
        "uso": "Per sottolineare l'importanza di iniziare bene"
    },
    {
        "proverbio": "Natale con i tuoi, Pasqua con chi vuoi",
        "significato": "Le feste importanti vanno passate in famiglia",
        "uso": "Per le festività"
    },
    {
        "proverbio": "Ogni lasciata è persa",
        "significato": "Le occasioni vanno colte al volo",
        "uso": "Per non rimandare"
    },
    {
        "proverbio": "Rosso di sera bel tempo si spera",
        "significato": "Un tramonto rosso preannuncia bel tempo",
        "uso": "Per previsioni meteo popolari"
    },
    {
        "proverbio": "Chi fa da sé fa per tre",
        "significato": "Facendo le cose da soli si ottengono risultati migliori",
        "uso": "Per esortare all'autonomia"
    },
    {
        "proverbio": "Paese che vai, usanza che trovi",
        "significato": "Ogni luogo ha le sue tradizioni",
        "uso": "Per accettare le diversità"
    },
]

PROVERBI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "proverbi_italiani",
        "description": (
            "Fornisce proverbi italiani con spiegazione."
            "Usare quando: dimmi un proverbio, saggezza popolare, proverbio italiano, "
            "che dice il proverbio, modi di dire"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "parola_chiave": {
                    "type": "string",
                    "description": "Parola chiave per cercare proverbio specifico"
                }
            },
            "required": [],
        },
    },
}

@register_function("proverbi_italiani", PROVERBI_FUNCTION_DESC, ToolType.WAIT)
def proverbi_italiani(conn, parola_chiave: str = None):
    logger.bind(tag=TAG).info(f"Proverbi: parola_chiave={parola_chiave}")

    if parola_chiave:
        # Cerca proverbio con parola chiave
        parola = parola_chiave.lower()
        trovati = [p for p in PROVERBI if parola in p["proverbio"].lower() or parola in p["significato"].lower()]

        if trovati:
            proverbio = random.choice(trovati)
        else:
            proverbio = random.choice(PROVERBI)
    else:
        proverbio = random.choice(PROVERBI)

    result = f"📜 **Proverbio italiano**\n\n"
    result += f"*\"{proverbio['proverbio']}\"*\n\n"
    result += f"**Significato**: {proverbio['significato']}\n"
    result += f"**Si usa**: {proverbio['uso']}"

    spoken = f"Ecco un proverbio: {proverbio['proverbio']}. "
    spoken += f"Significa che {proverbio['significato']}."

    return ActionResponse(Action.RESPONSE, result, spoken)
