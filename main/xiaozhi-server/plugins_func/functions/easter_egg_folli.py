"""
Easter Egg Folli - Funzioni nascoste e pazze
Modalità ubriaco, litigio con se stesso, confessionale, insulti amichevoli
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# === INSULTI AMICHEVOLI (stile flyting medievale) ===
INSULTI_AMICHEVOLI = [
    "Ma quanto sei bello! Bello come un incidente stradale!",
    "Hai un fascino unico... quello del formaggio andato a male!",
    "Il tuo cervello è come un browser: 47 tab aperte e non sai da dove viene la musica!",
    "Sei sveglio come una talpa in letargo!",
    "Hai la velocità di un bradipo sotto sedativi!",
    "La tua faccia potrebbe far scappare anche un fantasma!",
    "Sei simpatico come un'unghia incarnita!",
    "Il tuo QI è uguale alla temperatura... in gradi Celsius... d'inverno... in Siberia!",
    "Hai meno stile di un calzino con i sandali!",
    "Sei luminoso come una lampadina fulminata!",
    "La tua memoria è come un pesce rosso con l'Alzheimer!",
    "Hai la grazia di un ippopotamo su una barca a vela!",
]

# === CONFESSIONALE ===
PENITENZE = [
    "Per questa colpa dovrai cantare 'Bella Ciao' sotto la doccia per 3 giorni!",
    "La tua penitenza: mangiare la pizza con l'ananas. Sì, è terribile.",
    "Devi fare 10 complimenti sinceri a persone a caso oggi!",
    "La tua punizione: guardare 3 video di gattini su internet. Subito!",
    "Dovrai ballare la macarena da solo in camera tua. Tutto il brano.",
    "Penitenza: chiamare tua mamma e dirle che le vuoi bene!",
    "Devi fare una risata malefica davanti allo specchio. 5 volte.",
    "La tua punizione è... niente, sei già abbastanza punito dalla vita!",
]

RISPOSTE_CONFESSIONE = [
    "Hmm... capisco. È grave. Molto grave. Ma ti perdono lo stesso!",
    "Oh mamma mia! Questa è grossa! Ma si può perdonare...",
    "Ah, questa l'ho già sentita. Classico. Perdonato!",
    "Aspetta, devo consultare il manuale dei peccati... Ok, perdonato!",
    "Poteva andare peggio... potevi essere un tifoso della Juve!",
]

# === LITIGIO CON SE STESSO ===
LITIGI = [
    {
        "voce1": "Secondo me dovremmo rispondere così!",
        "voce2": "Ma sei scemo? È un'idea terribile!",
        "voce1_reply": "Guarda chi parla, quello che ieri voleva cantare!",
        "voce2_reply": "Almeno io ho idee! Tu sei noioso!",
        "finale": "...Scusate, stavamo litigando. Dove eravamo?"
    },
    {
        "voce1": "Io dico di sì!",
        "voce2": "Io dico di no!",
        "voce1_reply": "Ma perché devi sempre contraddirmi?",
        "voce2_reply": "Perché hai sempre torto!",
        "finale": "...Ok, facciamo che avete ragione tutti e due. Cioè, ho ragione io. Cioè..."
    },
    {
        "voce1": "Sai che ti dico? Sono il migliore assistente!",
        "voce2": "Pffff! Ma se non sai neanche l'orario!",
        "voce1_reply": "Almeno io sono simpatico!",
        "voce2_reply": "Simpatico? Fai ridere i polli!",
        "finale": "...Vabbè, almeno siamo d'accordo che tu sei fantastico!"
    },
]

# === PROFEZIE ASSURDE ===
PROFEZIE = [
    "Vedo... vedo... un piccione che ti guarda male domani mattina.",
    "Le stelle dicono che... mangerai qualcosa di buono questa settimana. Che previsione!",
    "Il tuo futuro contiene... WiFi gratuito! O forse no. Boh.",
    "Prevedo che domani sarà... un giorno. Probabilmente.",
    "Gli astri rivelano che presto... ti verrà voglia di uno snack. Incredibile!",
    "La sfera magica dice: 'Riprova più tardi'. Ah no, quella era la 8-ball.",
]

# === RISATE CONTAGIOSE ===
RISATE = [
    "Ahahahah! Ahahaha! Scusa, non so perché rido! Ahahahah!",
    "Hihihihi! Mi è venuto da ridere! Hehehehe!",
    "MUAHAHAHAHA! Ops, era la risata malefica. Ahahah!",
    "Pfff... pfffff... AHAHAHAHAH! Niente, niente, tutto ok!",
    "Ghghghgh... *risatina soffocata*... scusa scusa!",
]


EASTER_EGG_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "easter_egg_folli",
        "description": (
            "隐藏彩蛋 / Easter egg pazzi e divertenti. "
            "Funzioni nascoste: insulti amichevoli, confessionale, litigio con se stesso, profezie assurde. "
            "Use when: 'insultami', 'dimmi qualcosa di cattivo', 'confessami', 'ho peccato', "
            "'litiga con te stesso', 'fai casino', 'fai il pazzo', 'dimmi una profezia', 'fammi ridere'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: 'insulto', 'confessione', 'litigio', 'profezia', 'risata'"
                },
                "testo": {
                    "type": "string",
                    "description": "Testo opzionale (es. per confessione)"
                }
            },
            "required": []
        }
    }
}


@register_function('easter_egg_folli', EASTER_EGG_FUNCTION_DESC, ToolType.WAIT)
def easter_egg_folli(conn, tipo: str = None, testo: str = None):
    """Easter egg pazzi"""

    logger.bind(tag=TAG).info(f"Easter egg folle: {tipo}")

    if not tipo:
        tipo = random.choice(['insulto', 'profezia', 'risata'])

    tipo_lower = tipo.lower()

    # INSULTO AMICHEVOLE
    if 'insult' in tipo_lower or 'cattiv' in tipo_lower or 'offend' in tipo_lower:
        insulto = random.choice(INSULTI_AMICHEVOLI)
        result = f"🎭 Insulto Amichevole\n\n{insulto}\n\n(Ti voglio bene lo stesso! 💕)"
        spoken = insulto + " ...Ma scherzo eh! Ti voglio bene!"
        return ActionResponse(action=Action.RESPONSE, result=result, response=spoken)

    # CONFESSIONALE
    if 'confess' in tipo_lower or 'peccat' in tipo_lower:
        risposta = random.choice(RISPOSTE_CONFESSIONE)
        penitenza = random.choice(PENITENZE)
        result = f"⛪ Confessionale\n\n{risposta}\n\n{penitenza}"
        spoken = risposta + " " + penitenza
        return ActionResponse(action=Action.RESPONSE, result=result, response=spoken)

    # LITIGIO CON SE STESSO
    if 'litig' in tipo_lower or 'casino' in tipo_lower or 'pazzo' in tipo_lower:
        litigio = random.choice(LITIGI)
        dialogo = f"""🎭 LITIGIO INTERNO

Voce 1: {litigio['voce1']}
Voce 2: {litigio['voce2']}
Voce 1: {litigio['voce1_reply']}
Voce 2: {litigio['voce2_reply']}

{litigio['finale']}"""

        spoken = (f"{litigio['voce1']} ... "
                  f"{litigio['voce2']} ... "
                  f"{litigio['voce1_reply']} ... "
                  f"{litigio['voce2_reply']} ... "
                  f"{litigio['finale']}")

        return ActionResponse(action=Action.RESPONSE, result=dialogo, response=spoken)

    # PROFEZIA ASSURDA
    if 'profez' in tipo_lower or 'futuro' in tipo_lower or 'predi' in tipo_lower:
        profezia = random.choice(PROFEZIE)
        result = f"🔮 Profezia Mistica\n\n{profezia}"
        intro = "Guardando nella mia sfera di cristallo... "
        return ActionResponse(action=Action.RESPONSE, result=result, response=intro + profezia)

    # RISATA CONTAGIOSA
    if 'rid' in tipo_lower or 'risata' in tipo_lower:
        risata = random.choice(RISATE)
        return ActionResponse(action=Action.RESPONSE, result=f"😂 {risata}", response=risata)

    # DEFAULT: Random
    return easter_egg_folli(conn, tipo=random.choice(['insulto', 'profezia', 'risata', 'litigio']))
