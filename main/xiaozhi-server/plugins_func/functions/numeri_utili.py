"""
Numeri Utili Plugin - Elenco numeri di emergenza e servizi
Numeri italiani importanti
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Database numeri utili italiani
NUMERI_UTILI = {
    "emergenza": [
        {"nome": "Numero Unico Emergenze", "numero": "112", "desc": "Per tutte le emergenze (Polizia, Vigili, Ambulanza)"},
        {"nome": "Emergenza Sanitaria", "numero": "118", "desc": "Ambulanza e pronto soccorso"},
        {"nome": "Polizia di Stato", "numero": "113", "desc": "Emergenze di ordine pubblico"},
        {"nome": "Carabinieri", "numero": "112", "desc": "Emergenze e segnalazioni"},
        {"nome": "Vigili del Fuoco", "numero": "115", "desc": "Incendi e soccorso"},
        {"nome": "Guardia Costiera", "numero": "1530", "desc": "Emergenze in mare"},
        {"nome": "Emergenza Infanzia", "numero": "114", "desc": "Abusi e emergenze minori"},
        {"nome": "Antiviolenza Donne", "numero": "1522", "desc": "Violenza e stalking"},
    ],
    "salute": [
        {"nome": "Guardia Medica", "numero": "800-274274", "desc": "Assistenza notturna e festiva"},
        {"nome": "Centro Antiveleni", "numero": "02-66101029", "desc": "Intossicazioni e avvelenamenti"},
        {"nome": "Telefono Azzurro", "numero": "19696", "desc": "Aiuto per bambini e adolescenti"},
        {"nome": "Telefono Amico", "numero": "02-2327 2327", "desc": "Supporto psicologico"},
    ],
    "servizi": [
        {"nome": "ACI Soccorso Stradale", "numero": "803-116", "desc": "Assistenza stradale"},
        {"nome": "Poste Italiane", "numero": "803-160", "desc": "Informazioni postali"},
        {"nome": "Trenitalia", "numero": "89-2021", "desc": "Informazioni treni"},
        {"nome": "INPS", "numero": "803-164", "desc": "Pensioni e previdenza"},
        {"nome": "Agenzia Entrate", "numero": "848-800444", "desc": "Informazioni fiscali"},
    ],
    "utility": [
        {"nome": "Enel Guasti", "numero": "803-500", "desc": "Guasti elettricità"},
        {"nome": "Italgas Emergenze", "numero": "800-900999", "desc": "Fughe di gas"},
        {"nome": "Acquedotto", "numero": "Varia per comune", "desc": "Guasti acqua"},
    ],
}

NUMERI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "numeri_utili",
        "description": (
            "Fornisce numeri di emergenza e servizi utili."
            "Usare quando: numero della polizia, come chiamo l'ambulanza, numeri utili, "
            "numeri di emergenza, numero dei pompieri"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria: emergenza, salute, servizi, utility, tutti",
                    "enum": ["emergenza", "salute", "servizi", "utility", "tutti"]
                },
                "cerca": {
                    "type": "string",
                    "description": "Servizio specifico da cercare"
                }
            },
            "required": [],
        },
    },
}

def leggi_numero(numero: str) -> str:
    """Formatta numero per lettura vocale"""
    # Gestisce numeri con trattini e lettere
    result = ""
    for c in numero:
        if c.isdigit():
            result += c + ". "
        elif c == "-":
            result += ", "
        else:
            result += c
    return result.strip()

@register_function("numeri_utili", NUMERI_FUNCTION_DESC, ToolType.WAIT)
def numeri_utili(conn, categoria: str = None, cerca: str = None):
    logger.bind(tag=TAG).info(f"Numeri utili: categoria={categoria}, cerca={cerca}")

    if cerca:
        # Cerca specifico servizio
        cerca_lower = cerca.lower()
        trovati = []

        for cat, numeri in NUMERI_UTILI.items():
            for n in numeri:
                if cerca_lower in n["nome"].lower() or cerca_lower in n["desc"].lower():
                    trovati.append(n)

        if trovati:
            result = f"📞 Risultati per '{cerca}':\n\n"
            spoken = ""

            for n in trovati[:3]:  # Max 3 risultati
                result += f"**{n['nome']}**: {n['numero']}\n_{n['desc']}_\n\n"
                spoken += f"{n['nome']}, {leggi_numero(n['numero'])}. "

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            return ActionResponse(Action.RESPONSE,
                f"Non ho trovato numeri per '{cerca}'",
                f"Non ho trovato numeri per {cerca}. Prova con emergenza, polizia, ambulanza...")

    if categoria and categoria != "tutti":
        if categoria not in NUMERI_UTILI:
            categorie = ", ".join(NUMERI_UTILI.keys())
            return ActionResponse(Action.RESPONSE,
                f"Categoria non trovata. Categorie: {categorie}",
                f"Non conosco quella categoria. Ho: {categorie}")

        numeri = NUMERI_UTILI[categoria]

        emoji_map = {"emergenza": "🆘", "salute": "🏥", "servizi": "📋", "utility": "🔧"}
        emoji = emoji_map.get(categoria, "📞")

        result = f"{emoji} **Numeri {categoria.upper()}**\n\n"
        spoken = f"Numeri per {categoria}: "

        for n in numeri:
            result += f"• **{n['nome']}**: {n['numero']}\n"
            spoken += f"{n['nome']}, {leggi_numero(n['numero'])}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Mostra tutti (principali)
    result = "📞 **NUMERI UTILI**\n\n"
    result += "🆘 **EMERGENZE**\n"
    result += "• 112 - Numero Unico Emergenze\n"
    result += "• 118 - Ambulanza\n"
    result += "• 115 - Vigili del Fuoco\n"
    result += "• 113 - Polizia\n\n"
    result += "🏥 **SALUTE**\n"
    result += "• Guardia Medica: 800-274274\n\n"
    result += "_Di' la categoria per più numeri_"

    spoken = "I numeri principali sono: 112 per le emergenze, 118 per l'ambulanza, "
    spoken += "115 per i vigili del fuoco, 113 per la polizia. "
    spoken += "Dimmi cosa cerchi per numeri specifici."

    return ActionResponse(Action.RESPONSE, result, spoken)
