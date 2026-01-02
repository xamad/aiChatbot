"""
Compagno Notturno - Supporto per chi non riesce a dormire
Storie rilassanti, suoni della natura, tecniche di rilassamento
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Storie rilassanti per addormentarsi
STORIE_NOTTURNE = [
    {
        "titolo": "Il Faro sulla Scogliera",
        "storia": """C'era una volta un vecchio faro su una scogliera affacciata sul mare.
Ogni sera, il guardiano del faro accendeva la grande luce che guidava le navi nella notte.
Il mare era calmo quella sera, le onde sussurravano dolcemente contro le rocce.
Una, due, tre... le onde andavano e venivano, in un ritmo lento e costante.
Il guardiano si sedette sulla sua poltrona, ascoltando il suono del mare.
Le stelle brillavano nel cielo, una ad una si accendevano come piccole lanterne.
Il vento portava il profumo del sale e della brezza marina.
Tutto era pace, tutto era silenzio, solo il dolce suono delle onde..."""
    },
    {
        "titolo": "Il Giardino Segreto",
        "storia": """In fondo a un sentiero di campagna, nascosto tra gli alberi, c'era un giardino segreto.
I fiori dormivano con i petali chiusi, aspettando il sole del mattino.
Una fontana al centro gorgogliava piano, l'acqua scendeva dolcemente.
Le lucciole danzavano tra i cespugli, creando piccole stelle sulla terra.
Un vecchio salice piangente cullava i suoi rami nel vento leggero.
L'erba era morbida come un cuscino, fresca della rugiada serale.
Il profumo di gelsomino riempiva l'aria, dolce e avvolgente.
In questo giardino magico, il tempo si fermava, e tutto riposava in pace..."""
    },
    {
        "titolo": "La Nuvola di Cotone",
        "storia": """Immagina di sdraiarti su una nuvola morbida come cotone.
La nuvola ti avvolge dolcemente, leggera e calda.
Sotto di te, le luci delle città brillano come piccoli diamanti.
La luna ti sorride, grande e luminosa nel cielo stellato.
La nuvola ondeggia piano, cullandoti come una barca sul mare calmo.
Il vento soffia leggero, una carezza fresca sul viso.
Le stelle ti fanno compagnia, milioni di amiche silenziose.
Ti lasci andare, leggero come una piuma, cullato dalla notte..."""
    },
    {
        "titolo": "Il Treno della Notte",
        "storia": """Un vecchio treno viaggia silenzioso nella notte.
Il ritmo delle ruote sui binari è costante, rassicurante: tum-tum, tum-tum.
Fuori dal finestrino, i campi dormono sotto la luna.
Le luci dei paesini lontani brillano come stelle cadute.
Il vagone è caldo e accogliente, i sedili morbidi come nuvole.
Il treno attraversa ponti su fiumi argentati dalla luna.
Le montagne in lontananza sembrano giganti addormentati.
Tum-tum, tum-tum... il treno ti porta nel mondo dei sogni..."""
    },
    {
        "titolo": "La Biblioteca dei Sogni",
        "storia": """In una vecchia biblioteca, i libri dormono sugli scaffali.
La luce di una candela danza piano, creando ombre morbide.
Il profumo della carta antica riempie l'aria, dolce e rassicurante.
Una poltrona di velluto ti accoglie, morbida e avvolgente.
Il camino scoppietta piano, il fuoco canta la sua ninna nanna.
Fuori dalla finestra, la neve cade silenziosa, fiocco dopo fiocco.
I libri sussurrano storie antiche, favole di mondi lontani.
In questa biblioteca magica, ogni sogno trova la sua casa..."""
    }
]

# Tecniche di rilassamento
TECNICHE_RILASSAMENTO = [
    {
        "nome": "Respirazione 4-7-8",
        "istruzioni": """Facciamo insieme la respirazione quattro-sette-otto.
Mettiti comodo e chiudi gli occhi.
Inspira lentamente contando fino a quattro... uno, due, tre, quattro.
Trattieni il respiro contando fino a sette... uno, due, tre, quattro, cinque, sei, sette.
Espira lentamente contando fino a otto... uno, due, tre, quattro, cinque, sei, sette, otto.
Ripetiamo insieme... Inspira... uno, due, tre, quattro.
Trattieni... uno, due, tre, quattro, cinque, sei, sette.
Espira... uno, due, tre, quattro, cinque, sei, sette, otto.
Continua così, lasciando andare ogni pensiero con ogni respiro."""
    },
    {
        "nome": "Rilassamento Muscolare",
        "istruzioni": """Rilassiamo i muscoli uno alla volta.
Iniziamo dai piedi. Contrai i muscoli dei piedi per cinque secondi... e rilascia.
Senti come sono pesanti e rilassati.
Ora i polpacci. Contrai... e rilascia. Pesanti e morbidi.
Le cosce. Contrai... e rilascia. Tutto il peso si scioglie.
La pancia. Contrai... e rilascia. Respira piano.
Le mani. Stringi i pugni... e rilascia. Le dita si aprono.
Le spalle. Solleva verso le orecchie... e rilascia. Cadono pesanti.
Il viso. Contrai... e rilascia. Tutto morbido e sereno.
Tutto il corpo è pesante, rilassato, pronto per dormire."""
    },
    {
        "nome": "Visualizzazione della Spiaggia",
        "istruzioni": """Chiudi gli occhi e immagina una spiaggia al tramonto.
La sabbia è tiepida sotto i tuoi piedi, morbida e dorata.
Le onde arrivano piano sulla riva... e si ritirano... una dopo l'altra.
Il sole sta tramontando, colorando il cielo di arancione e rosa.
Una brezza leggera ti accarezza il viso, porta il profumo del mare.
Ti sdrai sulla sabbia calda, che si adatta al tuo corpo.
Ascolti il suono delle onde... avanti e indietro... avanti e indietro.
Il sole scende piano, la luce diventa più morbida.
Ti lasci cullare dal suono del mare, sempre più rilassato..."""
    }
]

# Pensieri rassicuranti
PENSIERI_NOTTE = [
    "La notte è fatta per riposare. Domani è un nuovo giorno.",
    "Ogni preoccupazione può aspettare fino a domani. Ora è tempo di pace.",
    "Il tuo corpo sa come dormire. Lascialo fare.",
    "Sei al sicuro. Tutto può aspettare.",
    "Il sonno arriverà. Non devi cercarlo, arriverà da solo.",
    "Respira piano. Ogni respiro ti porta più vicino al riposo.",
    "Le stelle vegliano su di te stanotte.",
    "Domani sarà un bel giorno. Ma ora, riposa.",
]


def get_ora_notte() -> str:
    """Restituisce saluto appropriato per l'ora"""
    ora = datetime.now().hour
    if 22 <= ora or ora < 4:
        return "buonanotte"
    elif 4 <= ora < 6:
        return "È molto presto"
    else:
        return "ciao"


COMPAGNO_NOTTURNO_DESC = {
    "type": "function",
    "function": {
        "name": "compagno_notturno",
        "description": (
            "Compagno notturno per chi non riesce a dormire. Storie, rilassamento, suoni. "
            "Usare per: non riesco a dormire, insonnia, raccontami una storia, "
            "aiutami a dormire, sono sveglio, notte, rilassamento, "
            "suoni natura, non prendo sonno, buonanotte"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo di aiuto notturno",
                    "enum": ["storia", "rilassamento", "suoni", "pensiero", "tutto"]
                }
            },
            "required": []
        }
    }
}


@register_function('compagno_notturno', COMPAGNO_NOTTURNO_DESC, ToolType.WAIT)
def compagno_notturno(conn, tipo: str = "tutto"):
    """Fornisce supporto notturno per chi non riesce a dormire"""

    logger.bind(tag=TAG).info(f"Compagno notturno richiesto: {tipo}")

    saluto = get_ora_notte()

    if tipo == "storia":
        storia = random.choice(STORIE_NOTTURNE)
        parlato = f"{saluto}. Ti racconto una storia per dormire. {storia['titolo']}. {storia['storia']}"
        display = f"🌙 **{storia['titolo']}**\n\n{storia['storia']}"

    elif tipo == "rilassamento":
        tecnica = random.choice(TECNICHE_RILASSAMENTO)
        parlato = f"{saluto}. Facciamo un po' di rilassamento insieme. {tecnica['istruzioni']}"
        display = f"🧘 **{tecnica['nome']}**\n\n{tecnica['istruzioni']}"

    elif tipo == "pensiero":
        pensiero = random.choice(PENSIERI_NOTTE)
        parlato = f"{saluto}. {pensiero}"
        display = f"💭 **Pensiero della notte**\n\n{pensiero}"

    else:  # "tutto" o "suoni" - mix rilassante
        pensiero = random.choice(PENSIERI_NOTTE)
        tecnica = random.choice(TECNICHE_RILASSAMENTO)
        storia = random.choice(STORIE_NOTTURNE)

        parlato = f"{saluto}. Sono qui con te. {pensiero} "
        parlato += f"Iniziamo con un po' di rilassamento. {tecnica['istruzioni']} "
        parlato += f"Ora ti racconto una storia. {storia['titolo']}. {storia['storia']}"

        display = f"🌙 **Compagno Notturno**\n\n"
        display += f"💭 {pensiero}\n\n"
        display += f"🧘 **{tecnica['nome']}**\n\n"
        display += f"📖 **{storia['titolo']}**"

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
