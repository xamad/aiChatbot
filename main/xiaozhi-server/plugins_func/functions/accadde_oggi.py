"""
Accadde Oggi Plugin - Eventi storici di oggi
Fatti importanti accaduti nella storia
"""

import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Database eventi storici per mese-giorno
EVENTI = {
    "01-01": [
        {"anno": 1948, "evento": "Entra in vigore la Costituzione italiana"},
        {"anno": 2002, "evento": "L'Euro diventa la valuta ufficiale in 12 paesi europei"},
        {"anno": 1801, "evento": "Giuseppe Piazzi scopre Cerere, il primo asteroide"},
    ],
    "01-06": [
        {"anno": 1907, "evento": "Maria Montessori apre la prima Casa dei Bambini a Roma"},
        {"anno": 1412, "evento": "Nasce Giovanna d'Arco"},
    ],
    "01-17": [
        {"anno": 1929, "evento": "Prima apparizione di Braccio di Ferro (Popeye)"},
        {"anno": 1773, "evento": "James Cook attraversa il Circolo Polare Antartico"},
    ],
    "02-14": [
        {"anno": 1929, "evento": "Strage di San Valentino a Chicago"},
        {"anno": 270, "evento": "San Valentino viene martirizzato"},
    ],
    "03-08": [
        {"anno": 1917, "evento": "Sciopero delle operaie a Pietrogrado, origine della Festa della Donna"},
    ],
    "03-17": [
        {"anno": 1861, "evento": "Proclamazione del Regno d'Italia"},
        {"anno": 461, "evento": "Morte di San Patrizio"},
    ],
    "03-25": [
        {"anno": 421, "evento": "Fondazione leggendaria di Venezia"},
    ],
    "04-15": [
        {"anno": 1912, "evento": "Affondamento del Titanic"},
        {"anno": 1452, "evento": "Nasce Leonardo da Vinci"},
    ],
    "04-21": [
        {"anno": -753, "evento": "Fondazione leggendaria di Roma"},
    ],
    "04-25": [
        {"anno": 1945, "evento": "Liberazione d'Italia dalla occupazione nazi-fascista"},
    ],
    "05-01": [
        {"anno": 1886, "evento": "Nasce la Festa dei Lavoratori dopo i fatti di Chicago"},
    ],
    "05-02": [
        {"anno": 1519, "evento": "Muore Leonardo da Vinci"},
    ],
    "06-02": [
        {"anno": 1946, "evento": "Referendum istituzionale: l'Italia diventa Repubblica"},
        {"anno": 1953, "evento": "Incoronazione della Regina Elisabetta II"},
    ],
    "06-24": [
        {"anno": 1509, "evento": "Enrico VIII viene incoronato Re d'Inghilterra"},
    ],
    "07-04": [
        {"anno": 1776, "evento": "Dichiarazione d'Indipendenza americana"},
    ],
    "07-14": [
        {"anno": 1789, "evento": "Presa della Bastiglia, inizio Rivoluzione Francese"},
    ],
    "07-20": [
        {"anno": 1969, "evento": "Neil Armstrong è il primo uomo sulla Luna"},
    ],
    "07-25": [
        {"anno": 1943, "evento": "Caduta del fascismo in Italia"},
    ],
    "08-06": [
        {"anno": 1945, "evento": "Bomba atomica su Hiroshima"},
    ],
    "08-15": [
        {"anno": 1945, "evento": "Fine della Seconda Guerra Mondiale"},
    ],
    "09-11": [
        {"anno": 2001, "evento": "Attentati terroristici alle Torri Gemelle"},
    ],
    "10-04": [
        {"anno": 1957, "evento": "L'URSS lancia lo Sputnik 1, primo satellite artificiale"},
    ],
    "10-12": [
        {"anno": 1492, "evento": "Cristoforo Colombo raggiunge le Americhe"},
    ],
    "10-28": [
        {"anno": 1922, "evento": "Marcia su Roma"},
    ],
    "11-09": [
        {"anno": 1989, "evento": "Caduta del Muro di Berlino"},
    ],
    "11-11": [
        {"anno": 1918, "evento": "Fine della Prima Guerra Mondiale"},
    ],
    "12-07": [
        {"anno": 1941, "evento": "Attacco giapponese a Pearl Harbor"},
    ],
    "12-25": [
        {"anno": 800, "evento": "Carlo Magno viene incoronato Imperatore"},
        {"anno": 1223, "evento": "San Francesco crea il primo presepe vivente"},
    ],
}

# Eventi generici per date non coperte
EVENTI_GENERICI = [
    {"anno": 1948, "evento": "La RAI inizia le trasmissioni regolari in Italia"},
    {"anno": 1961, "evento": "Yuri Gagarin è il primo uomo nello spazio"},
    {"anno": 1990, "evento": "Tim Berners-Lee inventa il World Wide Web"},
    {"anno": 1859, "evento": "Darwin pubblica 'L'origine delle specie'"},
    {"anno": 1903, "evento": "I fratelli Wright compiono il primo volo a motore"},
    {"anno": 1876, "evento": "Alexander Graham Bell inventa il telefono"},
]

ACCADDE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "accadde_oggi",
        "description": (
            "Racconta eventi storici accaduti oggi."
            "Usare quando: cosa accadde oggi, accadde oggi, nella storia, "
            "eventi storici, questo giorno nella storia"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data specifica (default: oggi)"
                }
            },
            "required": [],
        },
    },
}

@register_function("accadde_oggi", ACCADDE_FUNCTION_DESC, ToolType.WAIT)
def accadde_oggi(conn, data: str = None):
    logger.bind(tag=TAG).info(f"Accadde oggi: data={data}")

    if data:
        # Prova a parsare la data
        try:
            for fmt in ["%d/%m", "%d-%m", "%m-%d"]:
                try:
                    dt = datetime.strptime(data, fmt)
                    key = f"{dt.month:02d}-{dt.day:02d}"
                    break
                except:
                    continue
        except:
            key = datetime.now().strftime("%m-%d")
    else:
        key = datetime.now().strftime("%m-%d")

    oggi = datetime.now()
    mese, giorno = key.split("-")

    eventi = EVENTI.get(key, None)

    if not eventi:
        # Usa evento generico
        eventi = [random.choice(EVENTI_GENERICI)]

    # Formatta output
    result = f"📜 **ACCADDE OGGI** ({giorno}/{mese})\n\n"
    spoken = f"Accadde oggi, {giorno} del {mese}. "

    for e in eventi[:3]:  # Max 3 eventi
        anno = e["anno"]
        evento = e["evento"]

        if anno < 0:
            anno_str = f"{abs(anno)} a.C."
        else:
            anno_str = str(anno)

        result += f"• **{anno_str}**: {evento}\n\n"
        spoken += f"Nel {anno_str}, {evento}. "

    return ActionResponse(Action.RESPONSE, result, spoken)
