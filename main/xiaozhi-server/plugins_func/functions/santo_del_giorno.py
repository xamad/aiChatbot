"""
Santo del Giorno Plugin - Santi e onomastici
Chi si festeggia oggi
"""

from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Database santi per data (formato: "MM-DD": ["Santo1", "Santo2"])
SANTI = {
    # Gennaio
    "01-01": ["Maria Santissima Madre di Dio", "Fulgenzio"],
    "01-02": ["Basilio Magno", "Gregorio Nazianzeno"],
    "01-03": ["Genoveffa", "Daniele"],
    "01-04": ["Ermete", "Tito"],
    "01-05": ["Amelia", "Edoardo"],
    "01-06": ["Epifania del Signore", "Raffaela"],
    "01-07": ["Raimondo di Penyafort", "Luciano"],
    "01-08": ["Massimo", "Severino"],
    "01-09": ["Giuliano", "Adriano"],
    "01-10": ["Aldo", "Gregorio X"],
    "01-11": ["Igino", "Salvatore"],
    "01-12": ["Modesto", "Taziana"],
    "01-13": ["Ilario", "Ivette"],
    "01-14": ["Felice da Nola", "Dazio"],
    "01-15": ["Mauro", "Efisio"],
    "01-16": ["Marcello", "Tiziano"],
    "01-17": ["Antonio Abate", "Rosalina"],
    "01-18": ["Liberata", "Margherita d'Ungheria"],
    "01-19": ["Mario", "Marta"],
    "01-20": ["Sebastiano", "Fabiano"],
    "01-21": ["Agnese", "Meinardo"],
    "01-22": ["Vincenzo", "Gaudenzio"],
    "01-23": ["Emerenziana", "Ildefonso"],
    "01-24": ["Francesco di Sales", "Feliciano"],
    "01-25": ["Conversione di San Paolo", "Anania"],
    "01-26": ["Tito", "Timoteo"],
    "01-27": ["Angela Merici", "Giuliano"],
    "01-28": ["Tommaso d'Aquino", "Valerio"],
    "01-29": ["Valerio", "Costanzo"],
    "01-30": ["Martina", "Savina"],
    "01-31": ["Giovanni Bosco", "Marcella"],
    # Febbraio
    "02-01": ["Verdiana", "Severo"],
    "02-02": ["Presentazione del Signore", "Candlemas"],
    "02-03": ["Biagio", "Oscar"],
    "02-04": ["Gilberto", "Veronica"],
    "02-05": ["Agata", "Adelaide"],
    "02-06": ["Paolo Miki", "Dorotea"],
    "02-07": ["Riccardo", "Teodoro"],
    "02-08": ["Girolamo Emiliani", "Giuseppina"],
    "02-09": ["Apollonia", "Rinaldo"],
    "02-10": ["Scolastica", "Arnaldo"],
    "02-11": ["Nostra Signora di Lourdes", "Lourdes"],
    "02-12": ["Eulalia", "Damiano"],
    "02-13": ["Fosca", "Giordano"],
    "02-14": ["Valentino", "Cirillo"],
    "02-15": ["Faustino", "Giovita"],
    "02-16": ["Giuliana", "Onesimo"],
    "02-17": ["Donato", "Fondatore Serviti"],
    "02-18": ["Simone", "Costanza"],
    "02-19": ["Corrado", "Mansueto"],
    "02-20": ["Eleuterio", "Amata"],
    "02-21": ["Pier Damiani", "Eleonora"],
    "02-22": ["Margherita da Cortona", "Isabelle"],
    "02-23": ["Policarpo", "Renzo"],
    "02-24": ["Mattia apostolo", "Sergio"],
    "02-25": ["Romeo", "Cesario"],
    "02-26": ["Alessandro", "Nestore"],
    "02-27": ["Gabriele dell'Addolorata", "Leandro"],
    "02-28": ["Romano", "Giusto"],
    "02-29": ["Augusto", "Oswald"],
    # Marzo
    "03-01": ["Albino", "Rosendo"],
    "03-02": ["Agnese di Boemia", "Simplicio"],
    "03-03": ["Cunegonda", "Tiziano"],
    "03-04": ["Casimiro", "Lucio"],
    "03-05": ["Adriano", "Focà"],
    "03-06": ["Coletta", "Vittorino"],
    "03-07": ["Perpetua", "Felicita"],
    "03-08": ["Giovanni di Dio", "Beata"],
    "03-09": ["Francesca Romana", "Domenico Savio"],
    "03-10": ["Simplicio", "Emiliano"],
    "03-11": ["Costantino", "Sofronio"],
    "03-12": ["Massimiliano", "Luigi Orione"],
    "03-13": ["Rodrigo", "Cristina"],
    "03-14": ["Matilde", "Eva"],
    "03-15": ["Luisa de Marillac", "Longino"],
    "03-16": ["Eriberto", "Giuliano"],
    "03-17": ["Patrizio", "Gertrude"],
    "03-18": ["Cirillo di Gerusalemme", "Salvatore"],
    "03-19": ["Giuseppe", "San Giuseppe"],
    "03-20": ["Claudia", "Martino"],
    "03-21": ["Benedetto", "Nicola di Flüe"],
    "03-22": ["Lea", "Benvenuto"],
    "03-23": ["Turibio", "Rebecca"],
    "03-24": ["Romolo di Fiesole", "Caterina di Svezia"],
    "03-25": ["Annunciazione del Signore", "Lucia"],
    "03-26": ["Emanuele", "Teodoro"],
    "03-27": ["Ruperto", "Augusta"],
    "03-28": ["Sisto III", "Castore"],
    "03-29": ["Secondo", "Bertoldo"],
    "03-30": ["Amedeo", "Leonida"],
    "03-31": ["Beniamino", "Guido"],
    # Aprile
    "04-01": ["Ugo", "Teodora"],
    "04-02": ["Francesco da Paola", "Maria Egiziaca"],
    "04-03": ["Riccardo", "Sisto I"],
    "04-04": ["Isidoro di Siviglia", "Benedetto"],
    "04-05": ["Vincenzo Ferreri", "Irene"],
    "04-06": ["Celestino", "Guglielmo"],
    "04-07": ["Giovanni Battista de La Salle", "Egesippo"],
    "04-08": ["Giulia Billiart", "Alberto"],
    "04-09": ["Maria di Cleofa", "Demetrio"],
    "04-10": ["Ezechiele", "Terenzio"],
    "04-11": ["Stanislao", "Gemma Galgani"],
    "04-12": ["Giulio I", "Zeno"],
    "04-13": ["Martino I", "Ida"],
    "04-14": ["Valeriano", "Lamberto"],
    "04-15": ["Annibale", "Damiano"],
    "04-16": ["Bernadette Soubirous", "Lamberto"],
    "04-17": ["Roberto", "Aniceto"],
    "04-18": ["Galdino", "Apollonio"],
    "04-19": ["Emma", "Leone IX"],
    "04-20": ["Adalgisa", "Teodoro"],
    "04-21": ["Anselmo", "Corrado"],
    "04-22": ["Leonida", "Caio"],
    "04-23": ["Giorgio", "Adalberto"],
    "04-24": ["Fedele da Sigmaringen", "Egberto"],
    "04-25": ["Marco evangelista", "San Marco"],
    "04-26": ["Cleto", "Marcellino"],
    "04-27": ["Zita", "Antimo"],
    "04-28": ["Pietro Chanel", "Valeria"],
    "04-29": ["Caterina da Siena", "Ava"],
    "04-30": ["Pio V", "Giuseppe Benedetto"],
    # Maggio
    "05-01": ["Giuseppe lavoratore", "Geremia"],
    "05-02": ["Atanasio", "Boris"],
    "05-03": ["Filippo", "Giacomo apostoli"],
    "05-04": ["Ciriaco", "Floriano"],
    "05-05": ["Irene", "Gottardo"],
    "05-06": ["Domenico Savio", "Pelagia"],
    "05-07": ["Flavia", "Gisella"],
    "05-08": ["Vittore", "Ida"],
    "05-09": ["Pacomio", "Gregorio"],
    "05-10": ["Alfio", "Gordiano"],
    "05-11": ["Fabio", "Ignazio"],
    "05-12": ["Nereo", "Achille"],
    "05-13": ["Nostra Signora di Fatima", "Fatima"],
    "05-14": ["Mattia apostolo", "Maria"],
    "05-15": ["Isidoro", "Dionisia"],
    "05-16": ["Ubaldo", "Simone Stock"],
    "05-17": ["Pasquale", "Restituta"],
    "05-18": ["Giovanni I", "Felice"],
    "05-19": ["Pietro Celestino", "Ivone"],
    "05-20": ["Bernardino da Siena", "Arcangelo"],
    "05-21": ["Vittorio", "Cristoforo"],
    "05-22": ["Rita da Cascia", "Giulia"],
    "05-23": ["Desiderio", "Giovanni"],
    "05-24": ["Maria Ausiliatrice", "Vincenzo"],
    "05-25": ["Beda il Venerabile", "Gregorio VII"],
    "05-26": ["Filippo Neri", "Eleuterio"],
    "05-27": ["Agostino di Canterbury", "Restituta"],
    "05-28": ["Emilio", "Germano"],
    "05-29": ["Massimino", "Orsola"],
    "05-30": ["Giovanna d'Arco", "Ferdinando III"],
    "05-31": ["Visitazione della Beata Vergine Maria", "Petronilla"],
    # Giugno
    "06-01": ["Giustino", "Pamela"],
    "06-02": ["Marcellino", "Erasmo"],
    "06-03": ["Carlo Lwanga", "Clotilde"],
    "06-04": ["Francesco Caracciolo", "Quirino"],
    "06-05": ["Bonifacio", "Doroteo"],
    "06-06": ["Norberto", "Claudio"],
    "06-07": ["Roberto di Westminster", "Vittorino"],
    "06-08": ["Medardo", "Armando"],
    "06-09": ["Efrem", "Primo"],
    "06-10": ["Landerico", "Diana"],
    "06-11": ["Barnaba apostolo", "Paola"],
    "06-12": ["Onofrio", "Guido"],
    "06-13": ["Antonio di Padova", "Sant'Antonio"],
    "06-14": ["Eliseo", "Metodio"],
    "06-15": ["Vito", "Modesto"],
    "06-16": ["Aureliano", "Quirico"],
    "06-17": ["Ranieri", "Gregorio"],
    "06-18": ["Calogero", "Gregorio Barbarigo"],
    "06-19": ["Romualdo", "Giuliana"],
    "06-20": ["Silverio", "Adalgisa"],
    "06-21": ["Luigi Gonzaga", "Demetria"],
    "06-22": ["Paolino da Nola", "Tommaso Moro"],
    "06-23": ["Lanfranco", "Giuseppe Cafasso"],
    "06-24": ["Natività di Giovanni Battista", "San Giovanni"],
    "06-25": ["Guglielmo", "Massimo"],
    "06-26": ["Vigilio", "Davide"],
    "06-27": ["Cirillo d'Alessandria", "Ladislao"],
    "06-28": ["Ireneo", "Marcella"],
    "06-29": ["Pietro e Paolo apostoli", "San Pietro"],
    "06-30": ["Primi martiri della Chiesa romana", "Lucina"],
    # Luglio - Dicembre (semplificato per brevità)
    "07-01": ["Ester", "Teobaldo"],
    "07-15": ["Bonaventura", "Rosalia"],
    "07-25": ["Giacomo apostolo", "San Giacomo"],
    "07-26": ["Anna e Gioacchino", "Sant'Anna"],
    "08-05": ["Madonna della Neve", "Emidio"],
    "08-10": ["Lorenzo", "San Lorenzo"],
    "08-15": ["Assunzione della Beata Vergine Maria", "Ferragosto"],
    "08-20": ["Bernardo di Chiaravalle", "Samuele"],
    "09-08": ["Natività della Beata Vergine Maria", "Adriano"],
    "09-21": ["Matteo apostolo", "San Matteo"],
    "09-29": ["Michele, Gabriele e Raffaele arcangeli", "San Michele"],
    "10-04": ["Francesco d'Assisi", "San Francesco"],
    "10-15": ["Teresa d'Avila", "Santa Teresa"],
    "10-31": ["Quintino", "Lucilla"],
    "11-01": ["Tutti i Santi", "Ognissanti"],
    "11-02": ["Commemorazione dei defunti", "Morti"],
    "11-04": ["Carlo Borromeo", "San Carlo"],
    "11-11": ["Martino di Tours", "San Martino"],
    "12-06": ["Nicola di Bari", "San Nicola"],
    "12-08": ["Immacolata Concezione", "Immacolata"],
    "12-13": ["Lucia", "Santa Lucia"],
    "12-24": ["Delfino", "Vigilia di Natale"],
    "12-25": ["Natale del Signore", "Santo Natale"],
    "12-26": ["Stefano", "Santo Stefano"],
    "12-27": ["Giovanni apostolo", "San Giovanni"],
    "12-31": ["Silvestro I", "San Silvestro"],
}

SANTO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "santo_del_giorno",
        "description": (
            "Dice il santo del giorno e onomastici."
            "Usare quando: che santo è oggi, chi si festeggia, onomastico, "
            "santo del giorno, buon onomastico"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data specifica (default: oggi)"
                },
                "cerca_nome": {
                    "type": "string",
                    "description": "Nome da cercare per onomastico"
                }
            },
            "required": [],
        },
    },
}

def get_santi_data(data_str: str = None) -> tuple:
    """Ottiene santi per una data specifica"""
    if data_str:
        # Prova a parsare la data
        try:
            from datetime import datetime
            # Formato MM-DD
            if "-" in data_str and len(data_str) <= 5:
                key = data_str
            else:
                # Prova altri formati
                for fmt in ["%d/%m", "%d-%m", "%d %m"]:
                    try:
                        dt = datetime.strptime(data_str, fmt)
                        key = f"{dt.month:02d}-{dt.day:02d}"
                        break
                    except:
                        continue
        except:
            key = datetime.now().strftime("%m-%d")
    else:
        key = datetime.now().strftime("%m-%d")

    santi = SANTI.get(key, ["Santo non trovato"])
    return key, santi

@register_function("santo_del_giorno", SANTO_FUNCTION_DESC, ToolType.WAIT)
def santo_del_giorno(conn, data: str = None, cerca_nome: str = None):
    logger.bind(tag=TAG).info(f"Santo: data={data}, cerca={cerca_nome}")

    if cerca_nome:
        # Cerca quando si festeggia un nome
        cerca = cerca_nome.lower()
        trovati = []

        for data_key, santi_list in SANTI.items():
            for santo in santi_list:
                if cerca in santo.lower():
                    mese, giorno = data_key.split("-")
                    trovati.append(f"{giorno}/{mese}: {santo}")

        if trovati:
            result = f"🎂 Onomastico di '{cerca_nome}':\n\n"
            result += "\n".join(trovati[:5])  # Max 5 risultati

            spoken = f"L'onomastico di {cerca_nome} si festeggia il " + ", il ".join([t.split(":")[0] for t in trovati[:3]])

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            return ActionResponse(Action.RESPONSE,
                f"Non ho trovato '{cerca_nome}' nel calendario",
                f"Mi dispiace, non ho trovato {cerca_nome} nel calendario dei santi")

    # Santo del giorno
    key, santi = get_santi_data(data)
    mese, giorno = key.split("-")

    oggi = datetime.now().strftime("%m-%d")
    if key == oggi:
        giorno_desc = "Oggi"
    else:
        giorno_desc = f"Il {giorno}/{mese}"

    santi_str = ", ".join(santi)

    result = f"⛪ {giorno_desc} si festeggia:\n\n"
    for s in santi:
        result += f"• {s}\n"

    spoken = f"{giorno_desc} si festeggia {santi_str}. "

    # Aggiungi auguri se è oggi
    if key == oggi:
        spoken += f"Auguri a tutti i {santi[0].split()[0]}!"

    return ActionResponse(Action.RESPONSE, result, spoken)
