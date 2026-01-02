"""
Calcolatrice Plugin - Calcoli matematici vocali
Supporta operazioni base, percentuali, potenze, radici
"""

import math
import re
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

CALCOLATRICE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "calcolatrice",
        "description": (
            "Esegue calcoli matematici."
            "Usare quando: quanto fa, calcola, più, meno, per, diviso, "
            "percentuale, radice quadrata, alla seconda"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Espressione matematica (es: '5+3', '15*8', '100-30%', 'sqrt(16)')"
                },
                "operation": {
                    "type": "string",
                    "description": "Tipo operazione: add, subtract, multiply, divide, percent, power, sqrt",
                    "enum": ["add", "subtract", "multiply", "divide", "percent", "power", "sqrt", "expression"]
                },
                "num1": {
                    "type": "number",
                    "description": "Primo numero"
                },
                "num2": {
                    "type": "number",
                    "description": "Secondo numero"
                }
            },
            "required": ["operation"],
        },
    },
}


def format_number(n: float) -> str:
    """Formatta numero per output vocale"""
    if n == int(n):
        return str(int(n))
    # Limita decimali
    formatted = f"{n:.4f}".rstrip('0').rstrip('.')
    return formatted


def safe_eval(expression: str) -> float:
    """Valuta espressione matematica in modo sicuro"""
    # Pulisci e normalizza
    expr = expression.lower()
    expr = expr.replace('x', '*').replace('×', '*')
    expr = expr.replace(':', '/').replace('÷', '/')
    expr = expr.replace('^', '**')
    expr = expr.replace(',', '.')

    # Gestisci percentuali
    # "100 - 30%" -> "100 - (100 * 30 / 100)"
    percent_pattern = r'(\d+\.?\d*)\s*([+\-])\s*(\d+\.?\d*)%'
    match = re.search(percent_pattern, expr)
    if match:
        base = float(match.group(1))
        op = match.group(2)
        perc = float(match.group(3))
        perc_value = base * perc / 100
        if op == '-':
            return base - perc_value
        else:
            return base + perc_value

    # Percentuale semplice "15% di 80"
    simple_perc = re.search(r'(\d+\.?\d*)%?\s*(?:di|of)\s*(\d+\.?\d*)', expr)
    if simple_perc:
        perc = float(simple_perc.group(1))
        base = float(simple_perc.group(2))
        return base * perc / 100

    # Radice quadrata
    sqrt_match = re.search(r'sqrt\((\d+\.?\d*)\)', expr)
    if sqrt_match:
        return math.sqrt(float(sqrt_match.group(1)))

    # Caratteri permessi per eval sicuro
    allowed = set('0123456789.+-*/()**')
    clean_expr = ''.join(c for c in expr if c in allowed or c == ' ')
    clean_expr = clean_expr.strip()

    if not clean_expr:
        raise ValueError("Espressione non valida")

    # Valuta
    return eval(clean_expr)


@register_function("calcolatrice", CALCOLATRICE_FUNCTION_DESC, ToolType.WAIT)
def calcolatrice(conn, operation: str = "expression", expression: str = None, num1: float = None, num2: float = None):
    logger.bind(tag=TAG).info(f"Calcolatrice: op={operation}, expr={expression}, n1={num1}, n2={num2}")

    try:
        result = None
        explanation = ""

        if operation == "add" and num1 is not None and num2 is not None:
            result = num1 + num2
            explanation = f"{format_number(num1)} più {format_number(num2)} fa {format_number(result)}"

        elif operation == "subtract" and num1 is not None and num2 is not None:
            result = num1 - num2
            explanation = f"{format_number(num1)} meno {format_number(num2)} fa {format_number(result)}"

        elif operation == "multiply" and num1 is not None and num2 is not None:
            result = num1 * num2
            explanation = f"{format_number(num1)} per {format_number(num2)} fa {format_number(result)}"

        elif operation == "divide" and num1 is not None and num2 is not None:
            if num2 == 0:
                return ActionResponse(Action.RESPONSE,
                    "Errore: divisione per zero",
                    "Non posso dividere per zero!")
            result = num1 / num2
            explanation = f"{format_number(num1)} diviso {format_number(num2)} fa {format_number(result)}"

        elif operation == "percent" and num1 is not None and num2 is not None:
            result = num2 * num1 / 100
            explanation = f"Il {format_number(num1)} percento di {format_number(num2)} è {format_number(result)}"

        elif operation == "power" and num1 is not None and num2 is not None:
            result = math.pow(num1, num2)
            explanation = f"{format_number(num1)} alla {format_number(num2)} fa {format_number(result)}"

        elif operation == "sqrt" and num1 is not None:
            if num1 < 0:
                return ActionResponse(Action.RESPONSE,
                    "Errore: radice di numero negativo",
                    "Non posso calcolare la radice quadrata di un numero negativo")
            result = math.sqrt(num1)
            explanation = f"La radice quadrata di {format_number(num1)} è {format_number(result)}"

        elif expression:
            result = safe_eval(expression)
            explanation = f"Il risultato è {format_number(result)}"

        else:
            return ActionResponse(Action.RESPONSE,
                "Specifica un'operazione",
                "Dimmi cosa vuoi calcolare")

        return ActionResponse(Action.RESPONSE,
            f"Risultato: {format_number(result)}",
            explanation)

    except ZeroDivisionError:
        return ActionResponse(Action.RESPONSE,
            "Errore: divisione per zero",
            "Non posso dividere per zero!")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore calcolo: {e}")
        return ActionResponse(Action.RESPONSE,
            f"Errore nel calcolo: {str(e)}",
            "Mi dispiace, non riesco a fare questo calcolo")
