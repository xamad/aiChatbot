"""
Osterie Goliardiche - Canti tradizionali da osteria
I famosi canti goliardici numerati da 1 a 1000
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Ritornello tradizionale
RITORNELLO = "Paraponziponzipò!"

# Osterie numerate con versi in stile goliardico tradizionale
OSTERIE = {
    0: "All'osteria numero zero, non c'era nessuno per davvero, solo il gatto del curato, che si leccava il suo gelato!",
    1: "All'osteria numero uno, non c'era nemmeno uno, solo la figlia del dottore, che si grattava dove le prudeva il cuore!",
    2: "All'osteria numero due, c'eran le gambe della virtù, una di qua e una di là, e in mezzo c'era la felicità!",
    3: "All'osteria numero tre, c'era la figlia del re, che sul sofà col colonnello, faceva un gioco assai bello!",
    4: "All'osteria numero quattro, c'era un bel ritratto, della marchesa col maggiordomo, che facevano... l'uomo!",
    5: "All'osteria numero cinque, la serva perde le mutande, le cerca su e le cerca giù, ma le mutande non ci son più!",
    6: "All'osteria numero sei, ci son le figlie dei notai, che per un soldo o poco più, ti fan vedere quel che non si vede più!",
    7: "All'osteria numero sette, ci son salsicce e polpette, ma la più buona del locale, è quella della moglie del maresciallo!",
    8: "All'osteria numero otto, il prete mangia il biscotto, ma non è mica quello del forno, è quello che si mangia giorno e giorno!",
    9: "All'osteria numero nove, piove e non piove, sotto l'ombrello della contessa, si fa una cosa che non si confessa!",
    10: "All'osteria numero dieci, ci trovi tutti i preci, che per far la penitenza, van con le suore senza licenza!",
    11: "All'osteria numero undici, il frate perde i calici, ma trova qualcos'altro di rotondo, che non sta in chiesa ma sta più in fondo!",
    12: "All'osteria numero dodici, le donne mostran le cosce, e gli uomini con gran piacere, si mettono tutti a bere!",
    13: "All'osteria numero tredici, porta sfortuna ma tu non ci credici, ché la fortuna ce l'ha chi osa, e osa chi fa... quella cosa!",
    15: "All'osteria numero quindici, la serva lava i calici, ma invece dell'acqua benedetta, usa qualcosa che più diletta!",
    20: "All'osteria numero venti, ci sono solo i penitenti, che per espiare i loro peccati, ne fanno altri raddoppiati!",
    21: "All'osteria numero ventuno, non c'è nemmeno uno, perché son tutti a letto, a fare quello che è vietato dal precetto!",
    25: "All'osteria numero venticinque, la monaca si toglie le mutande, le appende fuori dalla finestra, e il sagrestano gliele sequestra!",
    30: "All'osteria numero trenta, la cuoca è contenta, perché invece del mestolo, ha trovato qualcos'altro di più consolo!",
    33: "All'osteria numero trentatré, il parroco beve il caffè, ma insieme al caffelatte, ci mette anche le peccaminose ciambelle fratte!",
    40: "All'osteria numero quaranta, la suora canta, ma non è l'Ave Maria, è una canzone più allegria!",
    50: "All'osteria numero cinquanta, la vecchia si vanta, che nonostante l'età avanzata, è ancora ben... frequentata!",
    69: "All'osteria numero sessantanove, il prete si muove, in una posizione strana, che non sta nella Bibbia cristiana!",
    77: "All'osteria numero settantasette, le donne sono perfette, ma gli uomini son distratti, perché guardano i loro... ritratti!",
    88: "All'osteria numero ottantotto, il sagrestano fa il botto, ma non con le campane, bensì con le popolane!",
    99: "All'osteria numero novantanove, il vescovo si commuove, vedendo il posteriore, della moglie del signore!",
    100: "All'osteria numero cento, tira un gran vento, che solleva le gonne, di tutte quante le donne!",
    111: "All'osteria numero centoundici, ci son tutte le appendici, del libro del Kamasutra, che il frate studia in modo ultra!",
    123: "All'osteria numero centoventitré, la regina va dal re, ma il re dorme beato, e la regina va dal suo fante amato!",
    200: "All'osteria numero duecento, c'è grande fermento, perché la badessa col frate, fan cose molto... prelate!",
    222: "All'osteria numero duecentoventidue, le gambe sono due, ma quel che c'è in mezzo, ha un valore e un prezzo!",
    300: "All'osteria numero trecento, soffia ancora il vento, che porta via i vestiti, e restano tutti svestiti!",
    333: "All'osteria numero trecentotrentatré, si balla in tre, ma il gioco che si fa, richiede più intimità!",
    400: "All'osteria numero quattrocento, c'è un grande evento, la suora sposa il frate, e fan nozze molto... prelate!",
    444: "All'osteria numero quattrocentoquarantaquattro, il prete fa un ritratto, della perpetua senza veli, che prega senza aneli!",
    500: "All'osteria numero cinquecento, io mi lamento, perché il vino è finito, ma il piacere è infinito!",
    555: "All'osteria numero cinquecentocinquantacinque, la serva rompe le mutande, e il padrone con gran zelo, gliene regala un paio... con un buco in mezzo!",
    666: "All'osteria numero seicentosessantasei, il diavolo dice: ehi! Ma l'acquasanta benedetta, la usa la suora... in modo che diletta!",
    700: "All'osteria numero settecento, c'è un matrimonio lento, tra la monaca e il priore, che consumano con tanto amore!",
    777: "All'osteria numero settecentosettantasette, le carte son perfette, ma il poker che si gioca, è di un altro tipo che ti... sconquassa!",
    800: "All'osteria numero ottocento, tutti son contento, perché il monsignore, ha perso il suo... pudore!",
    888: "All'osteria numero ottocentottantotto, il prete è un po' dotto, conosce tutti i segreti, delle mogli e dei mariti!",
    900: "All'osteria numero novecento, c'è un gran fermento, perché scappano le suore, dietro al predicatore!",
    999: "All'osteria numero novecentonovantanove, il cuore si muove, verso cose proibite, ma tanto tanto gradite!",
    1000: "All'osteria numero mille, brillano le pupille, di chi ha visto la badessa, fare l'ultima confessa... col cardinale che la pressa!",
}

# Lista di numeri disponibili per selezione random
NUMERI_OSTERIE = list(OSTERIE.keys())

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
            "'osteria numero uno', 'osteria numero due', 'canta numero'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {
                    "type": "integer",
                    "description": "Numero specifico dell'osteria da cantare (opzionale, altrimenti random)"
                }
            },
            "required": []
        }
    }
}


def trova_osteria_vicina(numero: int) -> int:
    """Trova il numero di osteria più vicino disponibile"""
    if numero in OSTERIE:
        return numero
    # Trova il più vicino
    return min(NUMERI_OSTERIE, key=lambda x: abs(x - numero))


@register_function('osterie_goliardiche', OSTERIE_FUNCTION_DESC, ToolType.WAIT)
def osterie_goliardiche(conn, numero: int = None):
    """Canta un'osteria goliardica"""

    if numero is not None:
        # Numero specifico richiesto
        num_osteria = trova_osteria_vicina(numero)
        if num_osteria != numero:
            intro = f"Non conosco l'osteria numero {numero}, ma ti canto la numero {num_osteria}! "
        else:
            intro = ""
    else:
        # Selezione casuale
        num_osteria = random.choice(NUMERI_OSTERIE)
        intro = ""

    verso = OSTERIE[num_osteria]

    logger.bind(tag=TAG).info(f"Osteria numero {num_osteria} cantata!")

    # Costruisce la risposta cantata
    canto = f"{intro}🍷 Osteria numero {num_osteria}! Osteria numero {num_osteria}! 🍷\n\n"
    canto += f"🎵 {verso} 🎵\n\n"
    canto += f"🎶 {RITORNELLO} 🎶"

    # Versione parlata più naturale
    parlato = f"{intro}Osteria numero {num_osteria}! Osteria numero {num_osteria}! "
    parlato += f"{verso} "
    parlato += f"{RITORNELLO}"

    return ActionResponse(
        action=Action.RESPONSE,
        result=canto,
        response=parlato
    )
