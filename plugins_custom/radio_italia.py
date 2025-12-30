"""
Radio Italia Plugin - Riproduce stazioni radio italiane in streaming
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stazioni radio italiane con stream URL
RADIO_STATIONS = {
    "rai radio 1": {
        "name": "Rai Radio 1",
        "url": "https://icestreaming.rai.it/1.mp3",
        "desc": "Notizie e attualità"
    },
    "rai radio 2": {
        "name": "Rai Radio 2",
        "url": "https://icestreaming.rai.it/2.mp3",
        "desc": "Musica e intrattenimento"
    },
    "rai radio 3": {
        "name": "Rai Radio 3",
        "url": "https://icestreaming.rai.it/3.mp3",
        "desc": "Cultura e musica classica"
    },
    "radio deejay": {
        "name": "Radio DeeJay",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiodeejay/radiodeejay/play1.mp3",
        "desc": "Musica pop e dance"
    },
    "rtl 102.5": {
        "name": "RTL 102.5",
        "url": "https://streamingv2.shoutcast.com/rtl-1025",
        "desc": "Very Normal People"
    },
    "radio 105": {
        "name": "Radio 105",
        "url": "https://icecast.unitedradio.it/Radio105.mp3",
        "desc": "Musica e news"
    },
    "radio italia": {
        "name": "Radio Italia",
        "url": "https://radioitaliasmi.akamaized.net/hls/live/2093120/RADIOITALIA/stream01/streamPlaylist.m3u8",
        "desc": "Solo musica italiana"
    },
    "virgin radio": {
        "name": "Virgin Radio",
        "url": "https://icecast.unitedradio.it/Virgin.mp3",
        "desc": "Rock music"
    },
    "radio kiss kiss": {
        "name": "Radio Kiss Kiss",
        "url": "https://ice07.fluidstream.net/KissKiss.mp3",
        "desc": "Hit del momento"
    },
    "m2o": {
        "name": "m2o",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/m2o/m2o/play1.mp3",
        "desc": "Dance e elettronica"
    },
    "radio capital": {
        "name": "Radio Capital",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/capital/capital/play1.mp3",
        "desc": "Classic rock"
    },
    "rds": {
        "name": "RDS 100% Grandi Successi",
        "url": "https://stream.rds.it/rds64k.mp3",
        "desc": "Grandi successi"
    },
    "radio 24": {
        "name": "Radio 24",
        "url": "https://shoutcast.radio24.it/radio24",
        "desc": "News e informazione"
    },
    "radio zeta": {
        "name": "Radio Zeta",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiozeta/radiozeta/play1.mp3",
        "desc": "Future Hits - Musica giovane"
    },
    "radio freccia": {
        "name": "Radio Freccia",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiofreccia/radiofreccia/play1.mp3",
        "desc": "Rock italiano"
    },
    "radio monte carlo": {
        "name": "Radio Monte Carlo",
        "url": "https://streamcdnb10-4c4b867c89244861ac216426883d1ad0.msvdn.net/rmc/rmc/play1.mp3",
        "desc": "Musica raffinata"
    },
    "radio subasio": {
        "name": "Radio Subasio",
        "url": "https://onair15.xdevel.com/proxy/subasioplus?mp=/stream",
        "desc": "Musica italiana"
    },
}

RADIO_ITALIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "radio_italia",
        "description": (
            "Riproduce stazioni radio italiane in streaming. "
            "Stazioni disponibili: Rai Radio 1/2/3, Radio DeeJay, RTL 102.5, "
            "Radio 105, Radio Italia, Virgin Radio, Kiss Kiss, m2o, Radio Capital, RDS, Radio 24. "
            "Esempi: 'metti radio deejay', 'ascolta rtl', 'radio rai 1'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "station": {
                    "type": "string",
                    "description": "Nome della stazione radio (es: radio deejay, rtl 102.5, rai radio 1)",
                },
                "action": {
                    "type": "string",
                    "description": "Azione: play (avvia), stop (ferma), list (elenco stazioni)",
                    "enum": ["play", "stop", "list"]
                },
            },
            "required": ["action"],
        },
    },
}


def find_station(query: str) -> dict:
    """Trova la stazione radio più simile alla query"""
    query = query.lower().strip()

    # Match esatto
    if query in RADIO_STATIONS:
        return RADIO_STATIONS[query]

    # Match parziale
    for key, station in RADIO_STATIONS.items():
        if query in key or key in query:
            return station
        # Controlla anche il nome
        if query in station["name"].lower():
            return station

    return None


@register_function("radio_italia", RADIO_ITALIA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def radio_italia(conn, action: str = "list", station: str = None):
    logger.bind(tag=TAG).info(f"Radio Italia: action={action}, station={station}")

    if action == "list":
        result = "**Stazioni radio disponibili:**\n\n"
        for key, s in RADIO_STATIONS.items():
            result += f"- **{s['name']}**: {s['desc']}\n"
        result += "\nDi' 'metti [nome radio]' per ascoltare!"
        return ActionResponse(Action.REQLLM, result, None)

    if action == "stop":
        # TODO: implementare stop audio
        return ActionResponse(Action.REQLLM, "Radio fermata", None)

    if action == "play":
        if not station:
            return ActionResponse(Action.REQLLM,
                "Quale radio vuoi ascoltare? Di' 'metti radio deejay' o 'elenco radio'", None)

        found = find_station(station)
        if not found:
            stations_list = ", ".join([s["name"] for s in RADIO_STATIONS.values()])
            return ActionResponse(Action.REQLLM,
                f"Radio '{station}' non trovata. Stazioni disponibili: {stations_list}", None)

        # Restituisci URL per il player
        # Il sistema dovrebbe gestire la riproduzione audio
        result = {
            "action": "play_audio",
            "url": found["url"],
            "name": found["name"]
        }

        return ActionResponse(
            Action.REQLLM,
            f"Avvio **{found['name']}** - {found['desc']}\n\n[Streaming: {found['url']}]",
            None
        )

    return ActionResponse(Action.REQLLM, "Azione non riconosciuta", None)
