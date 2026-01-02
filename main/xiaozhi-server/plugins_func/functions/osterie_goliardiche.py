"""
Osterie Goliardiche - Canti tradizionali da osteria
I famosi canti goliardici numerati da 1 a 1000
Genera versi per qualsiasi numero richiesto
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Ritornello tradizionale
RITORNELLO = "Paraponziponzipò!"

# Rime per numeri
RIME_NUMERI = {
    "uno": ["nessuno", "qualcuno", "ciascuno", "ognuno", "bruno", "digiuno", "raduno"],
    "due": ["virtù", "più", "su", "giù", "tu", "blu", "tribù"],
    "tre": ["re", "perché", "caffè", "sé", "mercé", "ahimé"],
    "quattro": ["ritratto", "matto", "gatto", "piatto", "ratto", "patto"],
    "cinque": ["nessuno le vince", "si convince", "langue", "sangue"],
    "sei": ["bei", "lei", "miei", "dei", "rei", "nei"],
    "sette": ["barzellette", "polpette", "vedette", "calzette", "saette"],
    "otto": ["botto", "dotto", "motto", "sotto", "rotto", "lotto", "risotto"],
    "nove": ["muove", "piove", "dove", "uove", "promuove"],
    "dieci": ["preci", "greci", "beci", "ceci"],
    "undici": ["indici", "giudici", "calici"],
    "dodici": ["cosce", "mosce", "nosce"],
    "tredici": ["credici", "medici"],
    "venti": ["lenti", "denti", "penti", "venti", "argenti"],
    "trenta": ["contenta", "polenta", "lenta", "spenta"],
    "quaranta": ["canta", "santa", "tanta", "incanta"],
    "cinquanta": ["vanta", "pianta", "ammanta"],
    "sessanta": ["infanta", "supplanta"],
    "settanta": ["ammanta", "decanta"],
    "ottanta": ["affranta", "rimpianta"],
    "novanta": ["infranta", "costanta"],
    "cento": ["contento", "convento", "lento", "vento", "fermento", "tormento", "evento"],
}

# Personaggi e situazioni tradizionali
PERSONAGGI = [
    "la figlia del dottore", "la moglie del fattore", "la serva del curato",
    "la suora del convento", "la perpetua del prete", "la contessa del castello",
    "la marchesa col marchese", "la regina senza re", "la monaca col frate",
    "la cuoca del maniero", "la fantesca del notaio", "la vedova allegra",
    "la moglie del podestà", "la figlia dell'oste", "la nipote del monsignore"
]

AZIONI = [
    "che faceva cose strane", "che ballava la tarantella",
    "che cantava a squarciagola", "che rideva a crepapelle",
    "che giocava a nascondino", "che perdeva le mutande",
    "che beveva il vino buono", "che mangiava le polpette",
    "che suonava il mandolino", "che dormiva nel fienile",
    "che si dava un gran da fare", "che non stava mai ferma",
    "che faceva penitenza", "che diceva le preghiere",
    "che guardava dalla finestra"
]

FINALI = [
    "e nessuno sapeva perché!", "ma lei era felice così!",
    "col sorriso sulle labbra!", "finché non spuntò il sole!",
    "e tutti applaudivano!", "che spettacolo fu!",
    "e il vino scorreva a fiumi!", "tra le risate generali!",
    "mentre il prete benediceva!", "e la banda suonava!",
    "sotto gli occhi del sagrestano!", "alla faccia del podestà!"
]

def numero_in_parole(n: int) -> str:
    """Converte numero in parole italiane"""
    unita = ["", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]
    decine = ["", "dieci", "venti", "trenta", "quaranta", "cinquanta",
              "sessanta", "settanta", "ottanta", "novanta"]
    speciali = {11: "undici", 12: "dodici", 13: "tredici", 14: "quattordici",
                15: "quindici", 16: "sedici", 17: "diciassette", 18: "diciotto", 19: "diciannove"}

    if n == 0:
        return "zero"
    if n < 10:
        return unita[n]
    if n < 20:
        return speciali.get(n, f"{decine[1]}{unita[n-10]}")
    if n < 100:
        d, u = divmod(n, 10)
        if u == 1 or u == 8:
            return decine[d][:-1] + unita[u]
        return decine[d] + unita[u]
    if n < 1000:
        c, resto = divmod(n, 100)
        centinaia = "cento" if c == 1 else f"{unita[c]}cento"
        if resto == 0:
            return centinaia
        return centinaia + numero_in_parole(resto)
    if n == 1000:
        return "mille"
    return str(n)

def trova_rima(num_parole: str) -> str:
    """Trova una rima per il numero"""
    # Cerca rima diretta
    for key, rime in RIME_NUMERI.items():
        if key in num_parole:
            return random.choice(rime)

    # Rima generica basata sull'ultima sillaba
    if num_parole.endswith("o"):
        return random.choice(["bello", "quello", "castello", "cappello"])
    if num_parole.endswith("e"):
        return random.choice(["signore", "amore", "cuore", "sapore"])
    if num_parole.endswith("i"):
        return random.choice(["baci", "audaci", "sagaci"])
    if num_parole.endswith("a"):
        return random.choice(["sera", "schiera", "maniera", "bandiera"])

    return random.choice(["amore", "cuore", "sapore", "signore"])

def genera_verso_osteria(numero: int) -> str:
    """Genera un verso goliardico per il numero specificato"""
    num_parole = numero_in_parole(numero)
    personaggio = random.choice(PERSONAGGI)
    azione = random.choice(AZIONI)
    finale = random.choice(FINALI)

    # Versi speciali per alcuni numeri famosi
    versi_speciali = {
        1: "non c'era nemmeno uno, solo la figlia del dottore, che si grattava dove le prudeva il cuore!",
        2: "c'eran le gambe della virtù, una di qua e una di là, e in mezzo c'era la felicità!",
        3: "c'era la figlia del re, che sul sofà col colonnello, faceva un gioco assai bello!",
        4: "c'era un bel ritratto, della marchesa col maggiordomo, che facevano cose da uomo!",
        5: "la serva perde le mutande, le cerca su e le cerca giù, ma le mutande non ci son più!",
        6: "ci son le figlie dei notai, che per un soldo o poco più, ti fan vedere quel che non si vede più!",
        7: "ci son salsicce e polpette, e la più buona del locale, è quella della moglie del maresciallo!",
        8: "il prete mangia il biscotto, ma non è mica quello del forno, è quello che si gusta giorno per giorno!",
        9: "piove e non piove, sotto l'ombrello della contessa, si fa una cosa che non si confessa!",
        10: "ci trovi tutti i preci, che per far la penitenza, fan cose senza licenza!",
        13: "porta sfortuna ma tu non ci credici, ché la fortuna ce l'ha chi osa, e osa chi fa quella cosa!",
        17: "porta sfortuna dice la gente, ma all'oste non gliene importa niente!",
        21: "non c'è nemmeno uno, perché son tutti a letto, a fare quello che dà diletto!",
        33: "il parroco beve il caffè, ma insieme al caffelatte, ci mette cose assai fratte!",
        69: "il prete si muove, in una posizione strana, che non sta nella Bibbia cristiana!",
        77: "le donne sono perfette, ma gli uomini son distratti, perché guardano certi ritratti!",
        88: "il sagrestano fa il botto, non con le campane del convento, ma con le donne del paese, che spettacolo violento!",
        99: "il vescovo si commuove, vedendo il posteriore, della moglie del signore!",
        100: "tira un gran vento, che solleva le gonne, di tutte quante le donne!",
        666: "il diavolo dice: ehi! Ma l'acquasanta benedetta, la usa la suora in modo che diletta!",
        777: "le carte son perfette, ma il poker che si gioca, è di un tipo che ti straccia la brocca!",
        888: "il prete è assai dotto, conosce tutti i segreti, delle mogli e dei mariti indiscreti!",
        999: "il cuore si muove, verso cose proibite, ma tanto tanto gradite!",
        1000: "brillano le pupille, di chi ha visto la badessa, fare l'ultima confessa col cardinale che la stressa!",
    }

    if numero in versi_speciali:
        return versi_speciali[numero]

    # Genera verso dinamico
    rima = trova_rima(num_parole)
    return f"c'era {personaggio}, {azione}, {finale}"


OSTERIE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "osterie_goliardiche",
        "description": (
            "唱意大利小酒馆歌曲 / CANTA la canzone goliardica 'All'osteria numero X'. "
            "Canti tradizionali goliardici con il ritornello Paraponziponzipò. "
            "NON cerca ristoranti, CANTA una canzone! "
            "Use when: 'cantami', 'canta goliardica', 'paraponziponzipò', 'paraponzi', "
            "'canzone goliardica', 'canto goliardico', 'all osteria numero', "
            "'osteria numero uno', 'osteria numero due', 'canta numero', 'canta osteria'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {
                    "type": "integer",
                    "description": "Numero specifico dell'osteria da cantare (1-1000, opzionale = random)"
                }
            },
            "required": []
        }
    }
}


@register_function('osterie_goliardiche', OSTERIE_FUNCTION_DESC, ToolType.WAIT)
def osterie_goliardiche(conn, numero: int = None):
    """Canta un'osteria goliardica"""

    if numero is not None:
        # Numero specifico richiesto, limita a 1-1000
        num_osteria = max(1, min(1000, numero))
    else:
        # Selezione casuale con preferenza per numeri "classici"
        numeri_classici = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 21, 33, 69, 77, 88, 99, 100, 666, 777, 888, 999, 1000]
        if random.random() < 0.7:  # 70% classici
            num_osteria = random.choice(numeri_classici)
        else:  # 30% qualsiasi
            num_osteria = random.randint(1, 1000)

    num_parole = numero_in_parole(num_osteria)
    verso = genera_verso_osteria(num_osteria)

    logger.bind(tag=TAG).info(f"Osteria numero {num_osteria} ({num_parole}) cantata!")

    # Costruisce la risposta cantata
    canto = f"🍷 All'osteria numero {num_parole}! All'osteria numero {num_parole}! 🍷\n\n"
    canto += f"🎵 {verso} 🎵\n\n"
    canto += f"🎶 {RITORNELLO} 🎶"

    # Versione parlata più naturale per TTS
    parlato = f"All'osteria numero {num_parole}! All'osteria numero {num_parole}! "
    parlato += f"{verso} "
    parlato += f"{RITORNELLO}"

    return ActionResponse(
        action=Action.RESPONSE,
        result=canto,
        response=parlato
    )
