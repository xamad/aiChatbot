"""
Frase del Giorno Plugin - Citazioni motivazionali
Quote famose e pensieri ispiranti
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Citazioni famose
CITAZIONI = [
    {"frase": "La vita è quello che ti accade mentre sei impegnato a fare altri progetti.", "autore": "John Lennon"},
    {"frase": "Il modo migliore per predire il futuro è crearlo.", "autore": "Peter Drucker"},
    {"frase": "Nel mezzo delle difficoltà nascono le opportunità.", "autore": "Albert Einstein"},
    {"frase": "L'unico modo per fare un ottimo lavoro è amare quello che fai.", "autore": "Steve Jobs"},
    {"frase": "Non è mai troppo tardi per essere ciò che avresti potuto essere.", "autore": "George Eliot"},
    {"frase": "Il successo è la somma di piccoli sforzi, ripetuti giorno dopo giorno.", "autore": "Robert Collier"},
    {"frase": "Credi in te stesso e tutto sarà possibile.", "autore": "Anonimo"},
    {"frase": "La felicità non è qualcosa di pronto. Viene dalle tue azioni.", "autore": "Dalai Lama"},
    {"frase": "Il viaggio di mille miglia inizia con un singolo passo.", "autore": "Lao Tzu"},
    {"frase": "Non contare i giorni, fa che i giorni contino.", "autore": "Muhammad Ali"},
    {"frase": "Ogni giorno è una nuova opportunità per cambiare la tua vita.", "autore": "Anonimo"},
    {"frase": "La semplicità è la sofisticazione suprema.", "autore": "Leonardo da Vinci"},
    {"frase": "Fai di ogni giorno il tuo capolavoro.", "autore": "John Wooden"},
    {"frase": "Il segreto per andare avanti è iniziare.", "autore": "Mark Twain"},
    {"frase": "Sii il cambiamento che vuoi vedere nel mondo.", "autore": "Mahatma Gandhi"},
    {"frase": "La vita è breve. Sorridi finché hai ancora i denti.", "autore": "Anonimo"},
    {"frase": "Non smettere mai di sognare, perché sognare è gratis.", "autore": "Anonimo"},
    {"frase": "Chi ha paura di soffrire, soffre già di quello che teme.", "autore": "Michel de Montaigne"},
    {"frase": "Il pessimista vede difficoltà in ogni opportunità. L'ottimista vede opportunità in ogni difficoltà.", "autore": "Winston Churchill"},
    {"frase": "La creatività è l'intelligenza che si diverte.", "autore": "Albert Einstein"},
    {"frase": "Non è la montagna che conquistiamo, ma noi stessi.", "autore": "Edmund Hillary"},
    {"frase": "La fortuna non esiste: esiste il momento in cui il talento incontra l'opportunità.", "autore": "Seneca"},
    {"frase": "Chi vive sperando muore cantando.", "autore": "Proverbio italiano"},
    {"frase": "L'importante non è cadere, ma rialzarsi.", "autore": "Anonimo"},
    {"frase": "Tutto è difficile prima di diventare facile.", "autore": "Thomas Fuller"},
    {"frase": "La pazienza è amara, ma il suo frutto è dolce.", "autore": "Jean-Jacques Rousseau"},
    {"frase": "Conosci te stesso.", "autore": "Socrate"},
    {"frase": "Ama e fa' ciò che vuoi.", "autore": "Sant'Agostino"},
    {"frase": "Chi non risica non rosica.", "autore": "Proverbio italiano"},
    {"frase": "La mente è come un paracadute: funziona solo se si apre.", "autore": "Frank Zappa"},
]

# Categorie di frasi
CATEGORIE = {
    "motivazionale": [
        "Non arrenderti mai! Il tuo momento arriverà.",
        "Ogni ostacolo è un'opportunità mascherata.",
        "Tu sei più forte di quanto pensi.",
        "Oggi è un buon giorno per fare qualcosa di straordinario.",
        "Credi in te stesso, sempre!",
    ],
    "saggezza": [
        "La pazienza è la virtù dei forti.",
        "Chi va piano va sano e va lontano.",
        "Meglio un uovo oggi che una gallina domani.",
        "L'esperienza è la migliore maestra.",
        "Dal dire al fare c'è di mezzo il mare.",
    ],
    "positiva": [
        "Sorridi! La vita è bella.",
        "Ogni giorno porta con sé una nuova speranza.",
        "La felicità è una scelta quotidiana.",
        "Guarda il lato positivo di ogni situazione.",
        "Il sole splende sempre dopo la tempesta.",
    ],
}

FRASE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "frase_del_giorno",
        "description": (
            "Fornisce citazioni e frasi motivazionali."
            "Usare quando: frase del giorno, citazione, dimmi qualcosa di bello, "
            "frase motivazionale, pensiero del giorno, ispirami"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: citazione (autore famoso), motivazionale, saggezza, positiva",
                    "enum": ["citazione", "motivazionale", "saggezza", "positiva", "random"]
                }
            },
            "required": [],
        },
    },
}

@register_function("frase_del_giorno", FRASE_FUNCTION_DESC, ToolType.WAIT)
def frase_del_giorno(conn, tipo: str = "random"):
    logger.bind(tag=TAG).info(f"Frase: tipo={tipo}")

    if tipo == "citazione" or tipo == "random":
        # Citazione con autore - usa seed per consistenza giornaliera
        oggi = datetime.now().strftime("%Y%m%d")
        random.seed(hash(oggi + "citazione"))
        citazione = random.choice(CITAZIONI)
        random.seed()

        result = f"💭 **Frase del giorno**\n\n\"{citazione['frase']}\"\n\n— _{citazione['autore']}_"
        spoken = f"Ecco la frase del giorno: {citazione['frase']}. {citazione['autore']}."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if tipo in CATEGORIE:
        random.seed(hash(datetime.now().strftime("%Y%m%d") + tipo))
        frase = random.choice(CATEGORIE[tipo])
        random.seed()

        emoji = {"motivazionale": "💪", "saggezza": "🦉", "positiva": "☀️"}.get(tipo, "💭")

        result = f"{emoji} **Frase {tipo}**\n\n\"{frase}\""
        spoken = f"Ecco una frase {tipo}: {frase}"

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Default: citazione random
    citazione = random.choice(CITAZIONI)

    result = f"💭 **Pensiero**\n\n\"{citazione['frase']}\"\n\n— _{citazione['autore']}_"
    spoken = f"{citazione['frase']}. Lo disse {citazione['autore']}."

    return ActionResponse(Action.RESPONSE, result, spoken)
