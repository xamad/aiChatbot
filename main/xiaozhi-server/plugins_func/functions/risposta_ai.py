"""
Risposta AI - Usa il LLM Groq già configurato per rispondere a domande generiche
Nessuna API aggiuntiva richiesta - sfrutta l'LLM esistente del sistema
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()


RISPOSTA_AI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "risposta_ai",
        "description": (
            "FALLBACK - Solo per domande INFORMATIVE senza azione da compiere. "
            "NON USARE MAI SE l'utente dice: 'cerca', 'mostra', 'metti', 'accendi', 'fammi vedere', "
            "'trova', 'apri' - queste sono AZIONI che richiedono altre funzioni specifiche! "
            "NON USARE PER: immagini→cerca_immagini, gif→cerca_gif, meteo→meteo_italia, "
            "radio→radio_italia, timer→timer_sveglia, musica→play_music, ricette→ricette. "
            "USARE SOLO PER domande tipo: 'chi era Napoleone', 'cos'è il DNA', 'spiegami la gravità'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domanda": {
                    "type": "string",
                    "description": "Domanda informativa pura, senza richiesta di azione"
                }
            },
            "required": ["domanda"]
        }
    }
}


@register_function('risposta_ai', RISPOSTA_AI_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def risposta_ai(conn, domanda: str):
    """
    Risponde a domande generiche usando l'LLM Groq già configurato.
    Restituisce REQLLM per far elaborare la risposta al LLM principale.
    """

    if not domanda:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Non ho capito la domanda.",
            response="Scusa, non ho capito. Puoi ripetere la domanda?"
        )

    logger.bind(tag=TAG).info(f"Risposta AI per: {domanda[:50]}...")

    # Costruisci un prompt ottimizzato per risposte concise
    prompt = f"""Rispondi in italiano a questa domanda in modo chiaro e conciso (massimo 3-4 frasi).
Sii informativo ma naturale, come se stessi parlando con un amico.

Domanda: {domanda}

Risposta:"""

    # Restituisce REQLLM - il sistema passerà la domanda al LLM principale (Groq)
    # che genererà una risposta naturale
    return ActionResponse(
        action=Action.REQLLM,
        result=prompt,
        response=None
    )
