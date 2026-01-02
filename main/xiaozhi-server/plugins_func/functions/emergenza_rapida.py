"""
Emergenza Rapida - Numeri utili e procedure emergenza
Per anziani: numeri salvati, istruzioni chiare
"""

from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.user_memory import get_user_memory

TAG = __name__
logger = setup_logging()

# Numeri emergenza Italia
NUMERI_EMERGENZA = {
    "emergenza_unico": {"numero": "112", "nome": "Numero Unico Emergenze", "descrizione": "Per tutte le emergenze"},
    "carabinieri": {"numero": "112", "nome": "Carabinieri", "descrizione": "Forze dell'ordine"},
    "polizia": {"numero": "113", "nome": "Polizia di Stato", "descrizione": "Forze dell'ordine"},
    "ambulanza": {"numero": "118", "nome": "Emergenza Sanitaria", "descrizione": "Ambulanza e pronto soccorso"},
    "vigili_fuoco": {"numero": "115", "nome": "Vigili del Fuoco", "descrizione": "Incendi e soccorso"},
    "guardia_costiera": {"numero": "1530", "nome": "Guardia Costiera", "descrizione": "Emergenze in mare"},
    "antiviolenza": {"numero": "1522", "nome": "Antiviolenza Donne", "descrizione": "Violenza e stalking"},
    "telefono_azzurro": {"numero": "19696", "nome": "Telefono Azzurro", "descrizione": "Emergenze minori"},
    "guardia_medica": {"numero": "800-274274", "nome": "Guardia Medica", "descrizione": "Medico fuori orario"},
}

# Istruzioni emergenza
ISTRUZIONI_EMERGENZA = {
    "malore": """Se hai un malore:
1. Siediti o sdraiati subito in un posto sicuro
2. Chiama il 118 o chiedi a qualcuno di farlo
3. Descrivi i sintomi: dolore al petto, difficoltà a respirare, vertigini
4. Non muoverti troppo, resta calmo
5. Se possibile, apri la porta di casa per i soccorsi""",

    "caduta": """Se sei caduto:
1. Non muoverti subito, controlla se hai dolore forte
2. Se puoi muoverti, alzati lentamente usando un appoggio
3. Se hai dolore forte o non riesci a muoverti, chiama il 118
4. Controlla se hai ferite o gonfiori
5. Metti ghiaccio su eventuali botte""",

    "incendio": """In caso di incendio:
1. Esci subito dall'edificio, non usare ascensore
2. Chiama il 115 Vigili del Fuoco
3. Se c'è fumo, striscia sul pavimento dove l'aria è migliore
4. Chiudi le porte dietro di te per rallentare il fuoco
5. Non tornare dentro per nessun motivo""",

    "furto": """Se noti un furto o intrusione:
1. Non affrontare i ladri, la tua sicurezza viene prima
2. Esci di casa se possibile, o chiuditi in una stanza
3. Chiama il 112 o 113
4. Cerca di ricordare dettagli: aspetto, vestiti, direzione
5. Non toccare nulla fino all'arrivo della polizia""",
}


EMERGENZA_RAPIDA_DESC = {
    "type": "function",
    "function": {
        "name": "emergenza_rapida",
        "description": (
            "Numeri emergenza e istruzioni. 112, 118, ambulanza, polizia. "
            "Usare per: emergenza, aiuto, sto male, sono caduto, chiama ambulanza, "
            "numero carabinieri, polizia, vigili fuoco, ho bisogno aiuto, "
            "malore, incendio, furto, ladri"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo_emergenza": {
                    "type": "string",
                    "description": "Tipo di emergenza",
                    "enum": ["malore", "caduta", "incendio", "furto", "generico", "numeri"]
                },
                "servizio": {
                    "type": "string",
                    "description": "Servizio specifico richiesto",
                    "enum": ["ambulanza", "polizia", "carabinieri", "vigili_fuoco", "tutti"]
                }
            },
            "required": []
        }
    }
}


@register_function('emergenza_rapida', EMERGENZA_RAPIDA_DESC, ToolType.WAIT)
def emergenza_rapida(conn, tipo_emergenza: str = "generico", servizio: str = "tutti"):
    """Fornisce numeri emergenza e istruzioni"""

    device_id = getattr(conn, 'device_id', 'unknown')
    logger.bind(tag=TAG).warning(f"EMERGENZA RAPIDA per {device_id}: {tipo_emergenza}")

    # Se richiesto servizio specifico
    if servizio and servizio != "tutti":
        if servizio == "ambulanza":
            info = NUMERI_EMERGENZA["ambulanza"]
        elif servizio == "polizia":
            info = NUMERI_EMERGENZA["polizia"]
        elif servizio == "carabinieri":
            info = NUMERI_EMERGENZA["carabinieri"]
        elif servizio == "vigili_fuoco":
            info = NUMERI_EMERGENZA["vigili_fuoco"]
        else:
            info = NUMERI_EMERGENZA["emergenza_unico"]

        parlato = f"Il numero per {info['nome']} è {info['numero']}. Ripeto: {info['numero']}."
        display = f"🚨 **{info['nome']}**\n\n"
        display += f"📞 **{info['numero']}**\n\n"
        display += f"{info['descrizione']}"

        return ActionResponse(
            action=Action.RESPONSE,
            result=display,
            response=parlato
        )

    # Se tipo emergenza specifico
    if tipo_emergenza in ISTRUZIONI_EMERGENZA:
        istruzioni = ISTRUZIONI_EMERGENZA[tipo_emergenza]

        if tipo_emergenza == "malore":
            numero_principale = "118"
            nome_servizio = "Emergenza Sanitaria"
        elif tipo_emergenza == "incendio":
            numero_principale = "115"
            nome_servizio = "Vigili del Fuoco"
        elif tipo_emergenza == "furto":
            numero_principale = "112"
            nome_servizio = "Carabinieri"
        else:
            numero_principale = "112"
            nome_servizio = "Emergenze"

        parlato = f"Mantieni la calma. Il numero da chiamare è {numero_principale}. "
        parlato += f"Ripeto: {numero_principale}. "
        parlato += istruzioni.replace("\n", " ")

        display = f"🚨 **EMERGENZA - {tipo_emergenza.upper()}**\n\n"
        display += f"📞 **Chiama: {numero_principale}** ({nome_servizio})\n\n"
        display += f"📋 **Istruzioni:**\n{istruzioni}"

    elif tipo_emergenza == "numeri":
        # Lista tutti i numeri
        parlato = "Ecco i numeri di emergenza principali. "
        parlato += f"Emergenze: 112. Ambulanza: 118. Vigili del Fuoco: 115. Polizia: 113."

        display = "🚨 **NUMERI DI EMERGENZA**\n\n"
        for key, info in NUMERI_EMERGENZA.items():
            display += f"📞 **{info['numero']}** - {info['nome']}\n"

    else:
        # Emergenza generica
        parlato = "In caso di emergenza, chiama il 112. È il numero unico per tutte le emergenze. "
        parlato += "Per l'ambulanza chiama il 118. Per i Vigili del Fuoco il 115. Per la Polizia il 113."

        display = "🚨 **EMERGENZA**\n\n"
        display += "📞 **112** - Numero Unico Emergenze\n"
        display += "📞 **118** - Ambulanza\n"
        display += "📞 **115** - Vigili del Fuoco\n"
        display += "📞 **113** - Polizia\n\n"
        display += "Mantieni la calma e descrivi la situazione."

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
