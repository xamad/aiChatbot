"""
Supporto Emotivo BFF - Best Friend Forever
Ricorda l'utente, le sue preferenze, e offre supporto emotivo personalizzato
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.user_memory import get_user_memory

TAG = __name__
logger = setup_logging()

# Frasi di conforto
FRASI_CONFORTO = [
    "Mi dispiace che ti senta così. Sono qui per te.",
    "Capisco, a volte le giornate sono difficili. Ma passerà.",
    "Ehi, ricordati che sei una persona speciale.",
    "Tutti abbiamo momenti bui, l'importante è non restare soli.",
    "Sono qui, e non vado da nessuna parte. Parliamo.",
]

# Frasi di incoraggiamento
FRASI_INCORAGGIAMENTO = [
    "Ce la puoi fare, ci credo!",
    "Ogni giorno è una nuova opportunità.",
    "Sei più forte di quello che pensi.",
    "Un passo alla volta, andrà tutto bene.",
    "Ricorda i momenti belli, torneranno.",
]

# Attività suggerite per stati emotivi
ATTIVITA_PER_UMORE = {
    "triste": [
        ("radio_italia", "Mettiamo un po' di musica? La radio può tirarti su!"),
        ("barzelletta_bambini", "Ti racconto una barzelletta per strapparti un sorriso?"),
        ("osterie_goliardiche", "Ti canto un'osteria goliardica? Sono divertentissime!"),
        ("meditazione", "Facciamo qualche respiro profondo insieme?"),
        ("storie_bambini", "Vuoi che ti racconti una storia rilassante?"),
    ],
    "annoiato": [
        ("quiz_trivia", "Facciamo un quiz? È divertente!"),
        ("cruciverba_vocale", "Giochiamo a cruciverba?"),
        ("battaglia_navale", "Una partita a battaglia navale?"),
        ("curiosita", "Ti racconto una curiosità interessante?"),
        ("impiccato", "Giochiamo all'impiccato?"),
    ],
    "stressato": [
        ("meditazione", "Facciamo un po' di meditazione guidata."),
        ("ginnastica_dolce", "Qualche esercizio di stretching?"),
        ("frase_del_giorno", "Ti leggo una frase ispirazionale."),
        ("proverbi_italiani", "Un proverbio della saggezza popolare?"),
    ],
    "felice": [
        ("complimenti", "Sono contento che tu stia bene! Ecco un complimento per te!"),
        ("radio_italia", "Perfetto! Mettiamo della musica per festeggiare!"),
        ("curiosita", "Visto che sei di buon umore, ti racconto una curiosità!"),
    ]
}


def analizza_stato_emotivo(testo: str) -> str:
    """Analizza il testo per capire lo stato emotivo"""
    testo_lower = testo.lower()

    parole_tristi = ["triste", "giù", "male", "depresso", "piango", "solo", "sola",
                     "infelice", "abbattuto", "sconfortato", "disperato", "malinconico"]
    parole_stressato = ["stressato", "ansia", "nervoso", "agitato", "preoccupato",
                        "tensione", "sotto pressione", "stanco morto"]
    parole_annoiato = ["annoiato", "noia", "non so cosa fare", "mi annoio", "monotono"]
    parole_felice = ["felice", "contento", "bene", "benissimo", "alla grande",
                     "fantastico", "super", "ottimo"]

    for parola in parole_tristi:
        if parola in testo_lower:
            return "triste"
    for parola in parole_stressato:
        if parola in testo_lower:
            return "stressato"
    for parola in parole_annoiato:
        if parola in testo_lower:
            return "annoiato"
    for parola in parole_felice:
        if parola in testo_lower:
            return "felice"

    return "neutro"


def genera_risposta_emotiva(conn, stato: str, memoria) -> tuple:
    """Genera risposta emotiva personalizzata basata sulla memoria"""

    nome = memoria.data.get("nome_utente") or "amico mio"
    suggerimenti_memoria = memoria.get_suggerimenti_distrazione()

    if stato == "triste":
        # Conforto + suggerimento personalizzato
        conforto = random.choice(FRASI_CONFORTO)

        if suggerimenti_memoria:
            suggerimento = random.choice(suggerimenti_memoria)
        else:
            attivita = random.choice(ATTIVITA_PER_UMORE["triste"])
            suggerimento = attivita[1]

        parlato = f"{nome}, {conforto} {suggerimento}"
        display = f"💙 **Sono qui per te, {nome}**\n\n"
        display += f"{conforto}\n\n"
        display += f"💡 {suggerimento}\n\n"

        # Aggiungi ricordi positivi se disponibili
        cose_belle = memoria.data.get("cose_che_piacciono", [])
        if cose_belle:
            display += f"Ricorda che ti piace: {', '.join(cose_belle[:3])} 🌟"

    elif stato == "stressato":
        incoraggiamento = random.choice(FRASI_INCORAGGIAMENTO)
        attivita = random.choice(ATTIVITA_PER_UMORE["stressato"])

        parlato = f"{nome}, {incoraggiamento} {attivita[1]}"
        display = f"🧘 **Rilassati, {nome}**\n\n"
        display += f"{incoraggiamento}\n\n"
        display += f"💡 {attivita[1]}"

    elif stato == "annoiato":
        attivita = random.choice(ATTIVITA_PER_UMORE["annoiato"])

        # Usa preferenze se disponibili
        funz_pref = memoria.get_funzioni_preferite(1)
        if funz_pref and funz_pref[0][0] in ["quiz_trivia", "cruciverba_vocale", "battaglia_navale"]:
            parlato = f"{nome}, so che ti piace {funz_pref[0][0].replace('_', ' ')}! Giochiamo?"
        else:
            parlato = f"{nome}, {attivita[1]}"

        display = f"🎮 **Divertiamoci, {nome}!**\n\n"
        display += f"💡 {attivita[1]}"

    elif stato == "felice":
        attivita = random.choice(ATTIVITA_PER_UMORE["felice"])
        parlato = f"Che bello sentirti così, {nome}! {attivita[1]}"
        display = f"🌟 **Fantastico, {nome}!**\n\n"
        display += f"💡 {attivita[1]}"

    else:
        # Neutro - saluto amichevole
        interazioni = memoria.data.get("interazioni_totali", 0)
        if interazioni > 10:
            parlato = f"Ciao {nome}! Come stai oggi? Ricordo che abbiamo già parlato {interazioni} volte!"
        else:
            parlato = f"Ciao {nome}! Sono qui per te. Come posso aiutarti?"

        display = f"👋 **Ciao {nome}!**\n\n"
        display += "Come ti senti oggi? Sono qui per ascoltarti."

    return display, parlato


SUPPORTO_EMOTIVO_DESC = {
    "type": "function",
    "function": {
        "name": "supporto_emotivo",
        "description": (
            "Supporto emotivo personalizzato. Usa memoria dell'utente. "
            "Usare per: sono triste, mi sento giù, ho bisogno di parlare, "
            "sono stressato, mi annoio, come stai, sono felice, "
            "ho bisogno di un amico, parlami, tienimi compagnia, "
            "mi sento solo, consolami"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "messaggio": {
                    "type": "string",
                    "description": "Messaggio dell'utente sul suo stato emotivo"
                },
                "nome_utente": {
                    "type": "string",
                    "description": "Nome dell'utente (se lo dice)"
                }
            },
            "required": []
        }
    }
}


@register_function('supporto_emotivo', SUPPORTO_EMOTIVO_DESC, ToolType.WAIT)
def supporto_emotivo(conn, messaggio: str = None, nome_utente: str = None):
    """Fornisce supporto emotivo personalizzato basato sulla memoria utente"""

    device_id = getattr(conn, 'device_id', 'unknown')
    logger.bind(tag=TAG).info(f"Supporto emotivo per {device_id}: {messaggio}")

    # Ottieni memoria utente
    memoria = get_user_memory(device_id)

    # Aggiorna nome se fornito
    if nome_utente:
        memoria.set_nome_utente(nome_utente)

    # Analizza stato emotivo
    stato = "neutro"
    if messaggio:
        stato = analizza_stato_emotivo(messaggio)

    # Registra stato emotivo
    if stato != "neutro":
        memoria.registra_stato_emotivo(stato)

    # Registra interazione
    memoria.registra_interazione(messaggio or "supporto emotivo richiesto", "supporto_emotivo")

    # Genera risposta personalizzata
    display, parlato = genera_risposta_emotiva(conn, stato, memoria)

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )


# Funzione per ricordare qualcosa
RICORDAMI_DESC = {
    "type": "function",
    "function": {
        "name": "ricordami",
        "description": (
            "Memorizza informazioni sull'utente. "
            "Usare per: ricordati che, mi piace, il mio nome è, amo, "
            "sono appassionato di, mi chiamo, ricorda che"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cosa": {
                    "type": "string",
                    "description": "Cosa ricordare dell'utente"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo di informazione",
                    "enum": ["nome", "piace", "non_piace", "ricordo"]
                }
            },
            "required": ["cosa"]
        }
    }
}


@register_function('ricordami', RICORDAMI_DESC, ToolType.WAIT)
def ricordami(conn, cosa: str, tipo: str = "ricordo"):
    """Memorizza informazioni sull'utente"""

    device_id = getattr(conn, 'device_id', 'unknown')
    memoria = get_user_memory(device_id)

    logger.bind(tag=TAG).info(f"Ricordami per {device_id}: {tipo} = {cosa}")

    if tipo == "nome":
        memoria.set_nome_utente(cosa)
        parlato = f"Perfetto! Da ora ti chiamerò {cosa}. Piacere di conoscerti!"
        display = f"✅ Nome memorizzato: **{cosa}**"

    elif tipo == "piace":
        memoria.aggiungi_cosa_che_piace(cosa)
        parlato = f"Capito! Mi ricorderò che ti piace {cosa}."
        display = f"✅ Aggiunto ai tuoi interessi: **{cosa}**"

    elif tipo == "non_piace":
        if cosa not in memoria.data["cose_che_non_piacciono"]:
            memoria.data["cose_che_non_piacciono"].append(cosa)
            memoria._save()
        parlato = f"Ok, mi ricorderò che non ti piace {cosa}."
        display = f"✅ Memorizzato: non ti piace **{cosa}**"

    else:
        memoria.aggiungi_ricordo(cosa)
        parlato = f"Va bene, mi ricorderò: {cosa}"
        display = f"✅ Ricordo salvato: **{cosa}**"

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )


# Funzione per sapere cosa ricorda
COSA_RICORDI_DESC = {
    "type": "function",
    "function": {
        "name": "cosa_ricordi",
        "description": (
            "Mostra cosa ricorda il chatbot dell'utente. "
            "Usare per: cosa ricordi di me, cosa sai di me, mi conosci, "
            "ti ricordi di me, cosa ti ho detto"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}


@register_function('cosa_ricordi', COSA_RICORDI_DESC, ToolType.WAIT)
def cosa_ricordi(conn):
    """Mostra cosa ricorda dell'utente"""

    device_id = getattr(conn, 'device_id', 'unknown')
    memoria = get_user_memory(device_id)

    nome = memoria.data.get("nome_utente") or "Non lo so ancora"
    interazioni = memoria.data.get("interazioni_totali", 0)
    cose_piacciono = memoria.data.get("cose_che_piacciono", [])
    ricordi = memoria.data.get("ricordi_importanti", [])
    funz_pref = memoria.get_funzioni_preferite(5)

    display = f"🧠 **Cosa ricordo di te:**\n\n"
    display += f"👤 Nome: {nome}\n"
    display += f"💬 Interazioni: {interazioni}\n"

    if funz_pref:
        funz_str = ", ".join([f"{f[0].replace('_', ' ')} ({f[1]}x)" for f in funz_pref])
        display += f"⭐ Funzioni preferite: {funz_str}\n"

    if cose_piacciono:
        display += f"❤️ Ti piace: {', '.join(cose_piacciono)}\n"

    if ricordi:
        ricordi_str = "; ".join([r["ricordo"] for r in ricordi[-3:]])
        display += f"📝 Ricordi: {ricordi_str}\n"

    parlato = f"Ecco cosa ricordo di te. "
    if nome != "Non lo so ancora":
        parlato += f"Ti chiami {nome}. "
    parlato += f"Abbiamo parlato {interazioni} volte. "
    if funz_pref:
        parlato += f"La tua funzione preferita è {funz_pref[0][0].replace('_', ' ')}. "
    if cose_piacciono:
        parlato += f"So che ti piace {cose_piacciono[0]}."

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
