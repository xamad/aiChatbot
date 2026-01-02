"""
Allenamento Mentale Plugin - Esercizi cognitivi per anziani
Mantiene la mente attiva con giochi di memoria, calcolo e logica
"""

from plugins_func.register import register_function, ToolType, ActionResponse, Action
import random
from datetime import datetime

ALLENAMENTO_DESC = {
    "function": {
        "name": "allenamento_mentale",
        "description": "Esercizi mentali e giochi cognitivi. Usa quando l'utente vuole allenare la mente, fare esercizi di memoria, calcolo, indovinelli o giochi di parole.",
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo esercizio: memoria, calcolo, parole, indovinello, sequenza, casuale"
                },
                "difficolta": {
                    "type": "string",
                    "description": "Livello: facile, medio, difficile"
                }
            },
            "required": []
        }
    }
}

INDOVINELLI = [
    {"domanda": "Ha le mani ma non può applaudire. Cos'è?", "risposta": "L'orologio"},
    {"domanda": "Più è caldo e più è fresco. Cos'è?", "risposta": "Il pane"},
    {"domanda": "Ha i denti ma non morde. Cos'è?", "risposta": "Il pettine"},
    {"domanda": "Sale e scende ma non si muove. Cos'è?", "risposta": "La temperatura"},
    {"domanda": "Ha un occhio solo ma non vede. Cos'è?", "risposta": "L'ago"},
    {"domanda": "Ha le gambe ma non cammina. Cos'è?", "risposta": "Il tavolo"},
    {"domanda": "Si rompe appena lo nomini. Cos'è?", "risposta": "Il silenzio"},
    {"domanda": "Cade sempre ma non si fa mai male. Cos'è?", "risposta": "La pioggia"},
    {"domanda": "Ha la coda ma non è un animale. Cos'è?", "risposta": "La cometa"},
    {"domanda": "Entra in casa senza aprire la porta. Cos'è?", "risposta": "La luce del sole"},
]

PROVERBI_INCOMPLETI = [
    {"inizio": "Chi dorme non piglia...", "fine": "pesci"},
    {"inizio": "Meglio un uovo oggi che una gallina...", "fine": "domani"},
    {"inizio": "Rosso di sera...", "fine": "bel tempo si spera"},
    {"inizio": "Chi fa da sé...", "fine": "fa per tre"},
    {"inizio": "L'appetito vien...", "fine": "mangiando"},
    {"inizio": "Chi trova un amico trova...", "fine": "un tesoro"},
    {"inizio": "Il mattino ha l'oro...", "fine": "in bocca"},
    {"inizio": "A caval donato non si guarda...", "fine": "in bocca"},
    {"inizio": "Chi la fa...", "fine": "l'aspetti"},
    {"inizio": "Tra il dire e il fare c'è di mezzo...", "fine": "il mare"},
]

def esercizio_memoria():
    """Genera esercizio di memoria"""
    # Lista di parole da ricordare
    categorie = {
        "frutta": ["mela", "pera", "banana", "arancia", "uva"],
        "animali": ["cane", "gatto", "cavallo", "mucca", "gallina"],
        "città": ["Roma", "Milano", "Napoli", "Firenze", "Venezia"],
        "colori": ["rosso", "blu", "verde", "giallo", "bianco"],
    }

    categoria = random.choice(list(categorie.keys()))
    parole = random.sample(categorie[categoria], 3)

    return f"Esercizio di memoria! Ti dico tre parole, ripetile dopo di me: {', '.join(parole)}. Ora, che giorno è oggi? Bene! Adesso riesci a ripetermi le tre parole di prima?"

def esercizio_calcolo(difficolta="facile"):
    """Genera esercizio di calcolo"""
    if difficolta == "facile":
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        op = random.choice(["+", "-"])
        if op == "-" and a < b:
            a, b = b, a
        risultato = a + b if op == "+" else a - b
    elif difficolta == "medio":
        a = random.randint(10, 50)
        b = random.randint(1, 20)
        op = random.choice(["+", "-"])
        if op == "-" and a < b:
            a, b = b, a
        risultato = a + b if op == "+" else a - b
    else:
        a = random.randint(2, 12)
        b = random.randint(2, 10)
        op = "×"
        risultato = a * b

    return f"Calcolo mentale! Quanto fa {a} {op} {b}? Prenditi il tempo che ti serve... La risposta è {risultato}. Hai indovinato?"

def esercizio_parole():
    """Genera esercizio con parole e proverbi"""
    proverbio = random.choice(PROVERBI_INCOMPLETI)
    return f"Completa il proverbio! {proverbio['inizio']} Come continua? La risposta è: {proverbio['fine']}! Lo sapevi?"

def esercizio_sequenza(difficolta="facile"):
    """Genera sequenza numerica da completare"""
    if difficolta == "facile":
        start = random.randint(1, 10)
        step = random.choice([1, 2, 5])
        seq = [start + i*step for i in range(4)]
        risposta = start + 4*step
    else:
        start = random.randint(1, 5)
        seq = [start * (2**i) for i in range(4)]
        risposta = start * 16

    seq_str = ", ".join(map(str, seq))
    return f"Quale numero viene dopo? {seq_str}, ...? La risposta è {risposta}! Hai trovato la sequenza?"

def esercizio_indovinello():
    """Propone un indovinello"""
    indo = random.choice(INDOVINELLI)
    return f"Indovinello! {indo['domanda']} Pensaci un po'... La risposta è: {indo['risposta']}! L'avevi capito?"

@register_function('allenamento_mentale', ALLENAMENTO_DESC, ToolType.WAIT)
def allenamento_mentale(conn, tipo: str = "casuale", difficolta: str = "facile"):
    """Esercizi mentali per mantenere la mente attiva"""

    esercizi = {
        "memoria": esercizio_memoria,
        "calcolo": lambda: esercizio_calcolo(difficolta),
        "parole": esercizio_parole,
        "indovinello": esercizio_indovinello,
        "sequenza": lambda: esercizio_sequenza(difficolta),
    }

    if tipo == "casuale" or tipo not in esercizi:
        tipo = random.choice(list(esercizi.keys()))

    risultato = esercizi[tipo]()

    # Aggiungi incoraggiamento
    incoraggiamenti = [
        "Ottimo lavoro per tenere la mente in forma!",
        "Bravo! Questi esercizi fanno benissimo al cervello!",
        "Continua così! La mente va allenata ogni giorno!",
        "Fantastico! Vuoi provare un altro esercizio?",
    ]

    return ActionResponse(
        action=Action.RESPONSE,
        result=f"{risultato}\n\n{random.choice(incoraggiamenti)}"
    )
