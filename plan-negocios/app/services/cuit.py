"""Validación y normalización de CUIT."""

import re

_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar_cuit(valor: str) -> str:
    """Deja solo los 11 dígitos del CUIT (acepta guiones, puntos y espacios)."""
    return re.sub(r"\D", "", valor or "")


def cuit_valido(valor: str) -> bool:
    """Valida largo, prefijo y dígito verificador (módulo 11)."""
    cuit = normalizar_cuit(valor)
    if len(cuit) != 11:
        return False
    if cuit[:2] not in ("20", "23", "24", "25", "26", "27", "30", "33", "34"):
        return False
    suma = sum(int(d) * p for d, p in zip(cuit[:10], _PESOS))
    resto = suma % 11
    verificador = 0 if resto == 0 else 11 - resto
    if verificador == 10:
        return False
    return verificador == int(cuit[10])


def formatear_cuit(valor: str) -> str:
    cuit = normalizar_cuit(valor)
    if len(cuit) != 11:
        return valor
    return f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}"
