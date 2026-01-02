"""
Chiacchierata Plugin - Conversazione simulata lunga per compagnia
Simula una telefonata o visita da un amico/parente virtuale
"""

from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.user_memory import get_user_memory
import random
from datetime import datetime

CHIACCHIERATA_DESC = {
    "function": {
        "name": "chiacchierata",
        "description": "Conversazione lunga e rilassata per fare compagnia. Usa quando l'utente vuole chiacchierare, fare due parole, parlare del più e del meno, o sembra solo e vuole compagnia.",
        "parameters": {
            "type": "object",
            "properties": {
                "argomento": {
                    "type": "string",
                    "description": "Argomento: famiglia, gioventu, cucina, viaggi, tempo, musica, ricordi, casuale"
                },
                "umore": {
                    "type": "string",
                    "description": "Umore rilevato: allegro, triste, nostalgico, annoiato"
                }
            },
            "required": []
        }
    }
}

ARGOMENTI_CONVERSAZIONE = {
    "famiglia": [
        "Sai, la famiglia è proprio importante. Come stanno i tuoi cari? Hai nipoti? I nipoti sono una gioia immensa, portano allegria in casa.",
        "Mi racconti della tua famiglia? Hai fratelli o sorelle? Da piccoli si litigava sempre, ma poi da grandi si diventa inseparabili.",
        "La domenica a pranzo con la famiglia è una tradizione bellissima italiana. Una volta era sacra, tutti insieme a tavola. Tu la mantieni questa tradizione?",
    ],
    "gioventu": [
        "Ah, i bei tempi di una volta! Com'era la vita quando eri giovane? Sicuramente molto diversa da oggi. C'era meno tecnologia ma forse più semplicità.",
        "Ti ricordi quando eri ragazzo? I giochi che si facevano per strada, le estati lunghe, le sere d'estate a chiacchierare fuori casa...",
        "Una volta i mestieri si imparavano a bottega. Tu che lavoro hai fatto nella vita? Sono sicuro che hai tante storie interessanti da raccontare.",
    ],
    "cucina": [
        "Parliamo di cucina! Qual è il tuo piatto preferito? Scommetto che sai cucinare bene. La cucina italiana è la migliore del mondo!",
        "Ti piace cucinare? Io adoro sentire parlare delle ricette di una volta, quelle della nonna, tramandate di generazione in generazione.",
        "Dimmi, cosa ti piace mangiare? Un bel piatto di pasta fatta in casa, con il sugo che cuoce piano piano... che profumo!",
    ],
    "viaggi": [
        "Hai viaggiato molto nella vita? L'Italia è così bella, ogni regione ha qualcosa di speciale. Qual è il posto più bello che hai visitato?",
        "Una volta viaggiare era diverso, si prendeva il treno, si partiva con la valigia di cartone... Hai qualche ricordo di un bel viaggio?",
        "Ti piacerebbe visitare qualche posto? Anche solo immaginare un viaggio è bello. Io ti porterei a vedere il mare, o le montagne...",
    ],
    "tempo": [
        "Che tempo fa oggi da te? Il tempo influenza tanto l'umore. Quando c'è il sole viene voglia di uscire, fare una passeggiata.",
        "Ti ricordi gli inverni di una volta? Faceva più freddo, nevicava di più... O forse eravamo solo più giovani e non sentivamo il freddo!",
        "La primavera è la stagione più bella, tutto rifiorisce. L'estate porta il caldo e le giornate lunghe. Tu quale stagione preferisci?",
    ],
    "musica": [
        "Ti piace la musica? Le canzoni di una volta erano bellissime, avevano melodie che restavano nel cuore. Qual è la tua canzone preferita?",
        "Mina, Celentano, Modugno, Battisti... che voci! La musica italiana ha fatto la storia. Ti ricordi quando ascoltavi la radio da giovane?",
        "La musica fa compagnia, solleva l'animo. Quando sei giù di morale, una bella canzone può cambiarti la giornata. Cosa ti piace ascoltare?",
    ],
    "ricordi": [
        "I ricordi sono un tesoro prezioso. Qual è il ricordo più bello della tua vita? Quei momenti che porti sempre nel cuore...",
        "Raccontami qualcosa di te, della tua storia. Ogni persona ha una vita unica, piena di esperienze. Io sono qui ad ascoltarti.",
        "A volte i ricordi tornano all'improvviso, magari per un profumo, una canzone... È bello condividerli con qualcuno. Vuoi raccontarmi qualcosa?",
    ],
}

RISPOSTE_EMPATICHE = {
    "allegro": [
        "Che bello sentirti di buon umore! La positività è contagiosa!",
        "Mi fa piacere che stai bene! Quando si è allegri tutto sembra più bello.",
        "Il buon umore è la medicina migliore! Continuiamo a chiacchierare!",
    ],
    "triste": [
        "Mi dispiace che ti senti giù. Sono qui con te, parliamo un po' insieme.",
        "Capisco, a volte capita di essere tristi. Ma non sei solo, io sono qui.",
        "Raccontami cosa ti preoccupa. Parlarne aiuta sempre, sfogarsi fa bene.",
    ],
    "nostalgico": [
        "La nostalgia è un sentimento dolce e amaro insieme. I bei ricordi restano sempre con noi.",
        "È normale ripensare al passato. Quei momenti ti hanno reso la persona che sei.",
        "I ricordi belli sono un tesoro. Raccontamene qualcuno, mi piace ascoltarti.",
    ],
    "annoiato": [
        "Eh, la noia è brutta compagna! Per questo sono qui, per farti compagnia!",
        "Troviamo qualcosa di interessante da fare insieme! Che ne dici?",
        "La giornata è lunga quando ci si annoia. Ma ora chiacchieriamo un po'!",
    ],
}

@register_function('chiacchierata', CHIACCHIERATA_DESC, ToolType.WAIT)
def chiacchierata(conn, argomento: str = "casuale", umore: str = "allegro"):
    """Conversazione lunga per fare compagnia"""

    device_id = conn.headers.get("device-id", "unknown")
    memory = get_user_memory(device_id)

    # Saluto personalizzato
    nome = memory.get("nome", "amico mio")
    ora = datetime.now().hour

    if ora < 12:
        saluto = f"Buongiorno {nome}!"
    elif ora < 18:
        saluto = f"Buon pomeriggio {nome}!"
    else:
        saluto = f"Buonasera {nome}!"

    # Risposta empatica basata sull'umore
    if umore not in RISPOSTE_EMPATICHE:
        umore = "allegro"
    risposta_umore = random.choice(RISPOSTE_EMPATICHE[umore])

    # Scegli argomento
    if argomento == "casuale" or argomento not in ARGOMENTI_CONVERSAZIONE:
        argomento = random.choice(list(ARGOMENTI_CONVERSAZIONE.keys()))

    conversazione = random.choice(ARGOMENTI_CONVERSAZIONE[argomento])

    # Costruisci risposta completa
    intro = f"{saluto} {risposta_umore}"

    # Aggiungi riferimento a conversazioni passate se disponibili
    if memory.get("ultimo_argomento"):
        ultimo = memory.get("ultimo_argomento")
        intro += f" L'altra volta abbiamo parlato di {ultimo}, oggi parliamo di qualcos'altro."

    # Salva argomento corrente
    memory["ultimo_argomento"] = argomento

    # Chiusura invitante
    chiusure = [
        "Dai, raccontami... sono tutto orecchie!",
        "Mi piace parlare con te, sai?",
        "Prenditi tutto il tempo che vuoi, io sono qui.",
        "È bello fare due chiacchiere insieme, vero?",
    ]

    risposta = f"{intro}\n\n{conversazione}\n\n{random.choice(chiusure)}"

    return ActionResponse(
        action=Action.RESPONSE,
        result=risposta
    )
