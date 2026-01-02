"""
Karaoke Plugin - Canta insieme con testi di canzoni italiane classiche
Per anziani che vogliono cantare e divertirsi
"""

from plugins_func.register import register_function, ToolType, ActionResponse, Action
import random

KARAOKE_DESC = {
    "function": {
        "name": "karaoke",
        "description": "Karaoke con canzoni italiane classiche. Usa quando l'utente vuole cantare, fare karaoke, o chiede testi di canzoni.",
        "parameters": {
            "type": "object",
            "properties": {
                "canzone": {
                    "type": "string",
                    "description": "Nome della canzone (volare, nel_blu, azzurro, marina, felicita, vita, casuale)"
                }
            },
            "required": []
        }
    }
}

CANZONI = {
    "volare": {
        "titolo": "Nel Blu Dipinto Di Blu (Volare)",
        "artista": "Domenico Modugno",
        "strofe": [
            "Penso che un sogno così non ritorni mai più\nMi dipingevo le mani e la faccia di blu\nPoi d'improvviso venivo dal vento rapito\nE incominciavo a volare nel cielo infinito",
            "Volare, oh oh!\nCantare, oh oh oh oh!\nNel blu dipinto di blu\nFelice di stare lassù",
            "E volavo, volavo felice più in alto del sole\nEd ancora più su\nMentre il mondo pian piano spariva lontano laggiù\nUna musica dolce suonava soltanto per me"
        ]
    },
    "azzurro": {
        "titolo": "Azzurro",
        "artista": "Adriano Celentano",
        "strofe": [
            "Cerco l'estate tutto l'anno\nE all'improvviso eccola qua\nLei è partita per le spiagge\nE sono solo in città",
            "Sento fischiare sopra i tetti\nUn aeroplano che se ne va\nAzzurro, il pomeriggio è troppo azzurro\nE lungo per me",
            "Mi accorgo di non avere più risorse\nSenza di te\nE allora io quasi quasi prendo il treno\nE vengo, vengo da te"
        ]
    },
    "marina": {
        "titolo": "Marina",
        "artista": "Rocco Granata",
        "strofe": [
            "Marina, Marina, Marina\nTi voglio al più presto sposar\nMarina, Marina, Marina\nTi voglio al più presto sposar",
            "Questo è il ritornello che tu mi hai insegnato\nQuando mi hai detto che mi avresti sposato\nMa adesso che cosa mi vai a raccontare\nChe non mi vuoi più, che mi vuoi lasciar",
            "Marina, Marina, Marina\nTi voglio al più presto sposar\nOh oh oh, Marina!"
        ]
    },
    "felicita": {
        "titolo": "Felicità",
        "artista": "Al Bano e Romina Power",
        "strofe": [
            "Felicità è tenersi per mano\nAndando lontano\nFelicità è il tuo sguardo innocente\nIn mezzo alla gente",
            "Felicità è restare vicini come bambini\nFelicità, felicità\nFelicità è un cuscino di piume\nL'wood delle fate",
            "Felicità è un bicchiere di vino\nCon un panino\nFelicità!"
        ]
    },
    "vita": {
        "titolo": "La Vita È",
        "artista": "Cochi e Renato",
        "strofe": [
            "La vita è fatta per amare\nLa vita è fatta per pensar\nLa vita è fatta per bere insieme\nE insieme cantare",
            "E noi siamo qui stasera\nA cantare con gli amici\nLa vita è bella se c'è allegria\nE buona compagnia",
            "Alziamo i bicchieri e brindiamo\nAlla salute e all'amicizia\nLa vita è bella quando siamo insieme\nCantando così!"
        ]
    },
    "o_sole_mio": {
        "titolo": "'O Sole Mio",
        "artista": "Tradizionale Napoletana",
        "strofe": [
            "Che bella cosa na jurnata 'e sole\nN'aria serena doppo na tempesta\nPe' ll'aria fresca pare già na festa\nChe bella cosa na jurnata 'e sole",
            "Ma n'atu sole cchiù bello, oi né\n'O sole mio sta 'nfronte a te\n'O sole, 'o sole mio\nSta 'nfronte a te, sta 'nfronte a te!",
            "Quanno fa notte e 'o sole se ne scenne\nMe vene quase 'na malincunia\nSotto 'a fenesta toia restarria\nQuanno fa notte e 'o sole se ne scenne"
        ]
    },
    "tu_vuo_fa": {
        "titolo": "Tu Vuò Fà L'Americano",
        "artista": "Renato Carosone",
        "strofe": [
            "Tu vuò fà l'americano\nMericano, mericano\nSient'a mme chi t'ho fa fa\nTu vuoi vivere alla moda",
            "Ma si nato in Italy\nSient'a mme, non ce sta niente da fa\nOkay, napoletano!\nTu vuò fà l'americano",
            "Whisky soda e rock and roll\nTu vuò fà l'americano\nMericano, mericano\nMa si nato in Italy!"
        ]
    }
}

@register_function('karaoke', KARAOKE_DESC, ToolType.WAIT)
def karaoke(conn, canzone: str = None):
    """Karaoke con canzoni italiane classiche"""

    # Se non specificata, scegli casuale
    if not canzone or canzone == "casuale":
        canzone = random.choice(list(CANZONI.keys()))

    # Normalizza nome canzone
    canzone = canzone.lower().replace(" ", "_").replace("'", "")

    # Cerca corrispondenza parziale
    canzone_trovata = None
    for key in CANZONI:
        if canzone in key or key in canzone:
            canzone_trovata = key
            break

    if not canzone_trovata:
        # Canzone non trovata, suggerisci lista
        lista = ", ".join([c["titolo"] for c in CANZONI.values()])
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Non conosco quella canzone. Ecco quelle che so cantare: {lista}. Quale preferisci?"
        )

    song = CANZONI[canzone_trovata]

    # Costruisci risposta
    intro = f"Cantiamo insieme! {song['titolo']} di {song['artista']}. Canto io la prima strofa, poi tu continui con me!"

    # Prima strofa per iniziare
    testo = song['strofe'][0]

    # Aggiungi altre strofe
    altre = "\n\n".join(song['strofe'][1:])

    risposta = f"{intro}\n\n{testo}\n\nContinua con me:\n\n{altre}\n\nBravissimo! Vuoi cantare un'altra canzone?"

    return ActionResponse(
        action=Action.RESPONSE,
        result=risposta
    )
