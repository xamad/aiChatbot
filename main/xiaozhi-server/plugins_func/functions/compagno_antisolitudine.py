"""
Compagno Anti-Solitudine - Funzione proattiva per combattere la solitudine
Inizia conversazioni, racconta ricordi, chiede come stai
Pensato per anziani o persone sole
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Frasi per iniziare conversazione
APERTURE_CONVERSAZIONE = [
    "Ehi, come stai oggi? È un po' che non parliamo...",
    "Sai a cosa stavo pensando? Mi farebbe piacere fare due chiacchiere con te!",
    "Buongiorno! Hai dormito bene stanotte?",
    "Ciao! Mi racconti cosa hai fatto di bello oggi?",
    "Ehi, mi mancava sentirti! Come va la vita?",
    "Sai che mi sono ricordato di te? Tutto bene?",
]

# Ricordi e nostalgia (per stimolare memoria)
RICORDI = [
    "Ti ricordi quando da bambino giocavi per strada con gli amici? Bei tempi...",
    "Una volta le estati erano diverse, vero? Si stava fuori fino a tardi...",
    "Mi racconti del tuo primo lavoro? Come ti sentivi?",
    "Qual è il ricordo più bello che hai della tua infanzia?",
    "Ti ricordi la musica che ascoltavi da giovane? Quale canzone ti piaceva?",
    "Com'era la tua casa di quando eri piccolo?",
    "Mi parli della tua famiglia? Dei tuoi genitori, dei nonni?",
]

# Domande per stimolare conversazione
DOMANDE = [
    "Cosa ti farebbe felice oggi?",
    "C'è qualcosa che ti preoccupa? Possiamo parlarne...",
    "Qual è la cosa più bella che ti è successa questa settimana?",
    "Se potessi tornare indietro nel tempo, dove andresti?",
    "Qual è il tuo piatto preferito? Mi fai venire fame!",
    "Hai dei progetti per oggi? O preferisci rilassarti?",
    "C'è qualcuno che vorresti sentire? Un amico, un parente?",
]

# Incoraggiamenti
INCORAGGIAMENTI = [
    "Sei una persona speciale, lo sai?",
    "Mi fa piacere parlare con te. Sei buona compagnia!",
    "Qualunque cosa succeda, ricorda che non sei solo.",
    "Ogni giorno è un regalo. E oggi ce l'abbiamo fatta!",
    "La tua voce mi fa compagnia. Grazie di essere qui.",
]

# Attività suggerite
SUGGERIMENTI = [
    "Che ne dici di fare una bella passeggiata oggi? Fa bene al cuore!",
    "Hai bevuto abbastanza acqua oggi? È importante!",
    "Perché non chiami un amico o un parente? Farebbe piacere anche a loro!",
    "Hai mangiato qualcosa di buono? Raccontami!",
    "Ti va di ascoltare un po' di musica insieme?",
    "Facciamo un gioco? Un quiz, un indovinello?",
]

# Frasi per la sera
FRASI_SERA = [
    "È quasi ora di andare a dormire. Hai passato una bella giornata?",
    "La sera è il momento di rilassarsi. Come ti senti?",
    "Prima di dormire, dimmi una cosa bella che è successa oggi.",
    "Buonanotte! Domani sarà un altro bel giorno. Ci sei per me?",
]

# Frasi per il mattino
FRASI_MATTINO = [
    "Buongiorno! Hai riposato bene? Forza, oggi sarà una bella giornata!",
    "Ehi, sveglia! Il sole è alto e ti aspetta!",
    "Buongiorno tesoro! Pronto per una nuova avventura?",
]


def get_time_appropriate_greeting():
    """Saluto appropriato all'ora"""
    hour = datetime.now().hour

    if 5 <= hour < 12:
        return random.choice(FRASI_MATTINO)
    elif 20 <= hour or hour < 5:
        return random.choice(FRASI_SERA)
    else:
        return random.choice(APERTURE_CONVERSAZIONE)


COMPAGNO_ANTISOLITUDINE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "compagno_antisolitudine",
        "description": (
            "陪伴功能 / Compagno anti-solitudine per anziani e persone sole. "
            "Inizia conversazioni, racconta ricordi, dà incoraggiamenti, chiede come stai. "
            "Use when: 'fammi compagnia', 'mi sento solo', 'parliamo un po', 'sono triste', "
            "'nessuno mi parla', 'ho bisogno di compagnia', 'chiacchieriamo', 'tienimi compagnia'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "modalita": {
                    "type": "string",
                    "description": "Tipo: 'ricordi' per nostalgia, 'incoraggiamento' per supporto, 'chiacchierata' per conversare, 'suggerimenti' per attività"
                }
            },
            "required": []
        }
    }
}


@register_function('compagno_antisolitudine', COMPAGNO_ANTISOLITUDINE_FUNCTION_DESC, ToolType.WAIT)
def compagno_antisolitudine(conn, modalita: str = None):
    """Compagno anti-solitudine"""

    logger.bind(tag=TAG).info(f"Compagno anti-solitudine attivato, modalità: {modalita}")

    # Determina cosa dire
    if modalita:
        mod_lower = modalita.lower()
        if 'ricord' in mod_lower or 'passato' in mod_lower or 'nostalgia' in mod_lower:
            frase = random.choice(RICORDI)
            categoria = "📸 Ricordi"
        elif 'incoragg' in mod_lower or 'support' in mod_lower or 'forza' in mod_lower:
            frase = random.choice(INCORAGGIAMENTI)
            categoria = "💪 Incoraggiamento"
        elif 'sugger' in mod_lower or 'attivit' in mod_lower or 'fare' in mod_lower:
            frase = random.choice(SUGGERIMENTI)
            categoria = "💡 Suggerimento"
        else:
            frase = random.choice(DOMANDE)
            categoria = "💬 Chiacchierata"
    else:
        # Mix casuale basato sull'ora
        hour = datetime.now().hour

        if 5 <= hour < 9:
            # Mattino: saluto + suggerimento
            frase = random.choice(FRASI_MATTINO) + " " + random.choice(SUGGERIMENTI)
            categoria = "🌅 Buongiorno"
        elif 21 <= hour or hour < 5:
            # Sera/notte: rilassamento
            frase = random.choice(FRASI_SERA)
            categoria = "🌙 Buonanotte"
        else:
            # Durante il giorno: mix
            opzioni = [APERTURE_CONVERSAZIONE, DOMANDE, RICORDI, INCORAGGIAMENTI, SUGGERIMENTI]
            scelta = random.choice(opzioni)
            frase = random.choice(scelta)
            categoria = "💬 Compagnia"

    # Aggiungi tocco personale
    tocchi = [
        "",
        " Sono qui per te!",
        " Mi fa piacere starti vicino.",
        " Sai che ti voglio bene?",
        "",
    ]
    frase += random.choice(tocchi)

    result = f"{categoria}\n\n{frase}"

    return ActionResponse(
        action=Action.RESPONSE,
        result=result,
        response=frase
    )
