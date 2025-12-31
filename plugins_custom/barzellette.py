"""
Barzellette Plugin - Barzellette per adulti e bambini
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# ============ BARZELLETTE PER BAMBINI ============
BARZELLETTE_BAMBINI = [
    "Perché il libro di matematica è triste? Perché ha troppi problemi!",
    "Cosa fa un gallo in mezzo al mare? Galleggia!",
    "Perché la mucca va al cinema? Per vedere i muu-vie!",
    "Cosa dice un semaforo a un altro semaforo? Non guardarmi, mi sto cambiando!",
    "Perché il computer è andato dal dottore? Perché aveva un virus!",
    "Cosa fa un chicco di caffè quando incontra un altro? Si salutano: Ciao, come stai? Bene, grazie, sono a pezzi!",
    "Perché i fantasmi sono pessimi bugiardi? Perché si vede che sono trasparenti!",
    "Cosa fa un cane con il trapano? Scava scava!",
    "Perché la banana va dal dottore? Perché non si sbuccia bene!",
    "Come si chiama un cane senza zampe? Non importa, tanto non viene!",
    "Cosa dice un pesce quando sbatte contro un muro? Diga!",
    "Perché il pomodoro è rosso? Perché ha visto l'insalata che si spogliava!",
    "Cosa fa una lumaca su una tartaruga? Wheee, che velocità!",
    "Perché la sedia è andata dallo psicologo? Perché si sentiva seduta!",
    "Come si chiama un boomerang che non torna? Un bastone!",
    "Perché lo scheletro non va mai alle feste? Perché non ha il corpo per ballare!",
    "Cosa fa un topo in chiesa? Squittisce le preghiere!",
    "Perché il libro di storia piange? Perché il suo passato è troppo pesante!",
    "Come si chiama un dinosauro che dorme? Dino-ronf!",
    "Cosa fa una pecora che pratica karate? Beee-laaaa!",
    "Perché il fungo va sempre alle feste? Perché è un tipo spugnoso!",
    "Cosa dice il sale allo zucchero? Ciao dolcezza!",
    "Perché la matita è triste? Perché ha una vita appuntita!",
    "Cosa fa un mago sotto la pioggia? Si bagna come tutti!",
    "Perché il palloncino ha paura? Perché ha sentito che scoppiava dalla risata!",
]

# ============ BARZELLETTE ADULTI (sconce ma non volgari) ============
BARZELLETTE_ADULTI = [
    "Un uomo entra in un bar... e dice AHI! Era una barra di ferro.",
    "Perché gli uomini non ascoltano? Perché la birra non parla!",
    "Mia moglie mi ha detto: 'Scegli, o me o il calcio!' Mi mancherà...",
    "Ho chiesto a mia moglie cosa volesse per il suo compleanno. 'Qualcosa con diamanti' ha detto. Le ho comprato un mazzo di carte.",
    "Mio marito dice che non lo ascolto mai... o qualcosa del genere.",
    "Il matrimonio è come una passeggiata nel parco. Jurassic Park.",
    "Mia suocera è venuta a trovarci. Le ho chiesto quanto si fermava. 'Finché non ti disturbo' ha risposto. Non si è neanche seduta.",
    "Ho smesso di bere per sempre. Adesso bevo solo per oggi.",
    "Il dottore mi ha detto di smettere di organizzare cene intime per quattro. A meno che non siamo in tre.",
    "Mia moglie cucina così male che i ladri entrano in casa per rimettere le cose nel frigorifero.",
    "Ho chiesto al barista un doppio. Mi ha portato un sosia.",
    "La mia ragazza dice che sono troppo pigro. Ma non ho la forza di discuterne.",
    "Mio nonno diceva: 'Vai avanti. Non fermarti mai.' Era un ottimo autista di autobus.",
    "Ho un lavoro stabile. Lavoro in una scuderia.",
    "Il mio capo mi ha detto: 'Sei l'ultimo arrivato e il primo ad andare via.' Ho risposto: 'Grazie, adoro essere il migliore!'",
    "Ho comprato un libro sulla procrastinazione. Lo leggerò domani.",
    "Ho chiesto al cameriere: 'Questo pollo è fresco?' Ha risposto: 'Sì, stamattina era ancora surgelato.'",
    "Un ottimista vede il bicchiere mezzo pieno. Un pessimista mezzo vuoto. Io vedo che qualcuno ha bevuto la mia birra.",
    "Mia moglie dice che non la porto mai da nessuna parte. Le ho risposto: 'E la cucina? Ti ci porto ogni giorno!'",
    "Ho venduto il mio aspirapolvere. Tanto faceva solo polvere.",
    "Il dottore mi ha detto che devo smettere di fare cene per quattro... a meno che non ci siano altre tre persone.",
    "Ho una memoria fotografica. Peccato che non abbia pellicola.",
    "La mia dieta? Mangio quello che voglio e piango.",
    "Mia moglie mi ha lasciato perché sono troppo insicuro... No aspetta, è tornata! ...No se n'è andata.",
    "Ho provato a fare jogging ma il gelato cadeva dalla coppetta.",
]

BARZELLETTE_BAMBINI_DESC = {
    "type": "function",
    "function": {
        "name": "barzelletta_bambini",
        "description": (
            "讲儿童笑话 / Racconta una barzelletta per bambini. "
            "当用户想要一个笑话适合儿童时使用。"
            "Use when: 'barzelletta per bambini', 'joke for kids', 'racconta una barzelletta bambini'"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

BARZELLETTE_ADULTI_DESC = {
    "type": "function",
    "function": {
        "name": "barzelletta_adulti",
        "description": (
            "讲成人笑话 / Racconta una barzelletta per adulti (spiritosa, non volgare). "
            "当用户想要一个成人笑话、幽默的笑话时使用。"
            "Use when: 'barzelletta sconce', 'barzelletta adulti', 'adult joke', 'dirty joke', "
            "'barzelletta spinta', 'battuta per grandi'"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


@register_function("barzelletta_bambini", BARZELLETTE_BAMBINI_DESC, ToolType.SYSTEM_CTL)
def barzelletta_bambini(conn):
    """Racconta una barzelletta per bambini"""
    joke = random.choice(BARZELLETTE_BAMBINI)
    logger.bind(tag=TAG).info("Barzelletta bambini richiesta")
    return ActionResponse(Action.REQLLM, f"🎈 Ecco una barzelletta per te!\n\n{joke}", None)


@register_function("barzelletta_adulti", BARZELLETTE_ADULTI_DESC, ToolType.SYSTEM_CTL)
def barzelletta_adulti(conn):
    """Racconta una barzelletta per adulti"""
    joke = random.choice(BARZELLETTE_ADULTI)
    logger.bind(tag=TAG).info("Barzelletta adulti richiesta")
    return ActionResponse(Action.REQLLM, f"😏 Eccone una per te!\n\n{joke}", None)
