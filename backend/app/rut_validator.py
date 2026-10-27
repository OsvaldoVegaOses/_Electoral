import re

def clean_rut(rut: str) -> str:
    """Elimina puntos, guiones y espacios, dejando dígitos y K mayúscula"""
    if not rut:
        return ""
    cleaned = re.sub(r'[^0-9kK]', '', str(rut)).upper()
    return cleaned

def calculate_dv(rut_number: int) -> str:
    """Calcula el dígito verificador según Módulo 11 chileno"""
    factors = [2, 3, 4, 5, 6, 7]
    factor_index = 0
    total = 0
    
    for digit in reversed(str(rut_number)):
        total += int(digit) * factors[factor_index]
        factor_index = (factor_index + 1) % len(factors)
        
    remainder = total % 11
    dv = 11 - remainder
    
    if dv == 11:
        return "0"
    elif dv == 10:
        return "K"
    else:
        return str(dv)

def validate_rut(rut: str) -> bool:
    """Valida si un RUT chileno es matemáticamente correcto"""
    cleaned = clean_rut(rut)
    if len(cleaned) < 2:
        return False
        
    body = cleaned[:-1]
    given_dv = cleaned[-1]
    
    if not body.isdigit():
        return False
        
    expected_dv = calculate_dv(int(body))
    return given_dv == expected_dv

def format_rut(rut: str) -> str:
    """Formatea a formato estándar con puntos y guión: XX.XXX.XXX-X"""
    cleaned = clean_rut(rut)
    if len(cleaned) < 2:
        return rut
        
    body = cleaned[:-1]
    dv = cleaned[-1]
    
    # Formatear cuerpo con puntos
    reversed_body = body[::-1]
    grouped = [reversed_body[i:i+3] for i in range(0, len(reversed_body), 3)]
    formatted_body = ".".join(grouped)[::-1]
    
    return f"{formatted_body}-{dv}"


def mask_rut(rut: str) -> str:
    """
    Enmascara un RUT chileno para registros de auditoría y protección de PII.
    Ejemplos:
      - '12.345.678-5' -> '12.***.***-5'
      - '9.876.543-K'  -> '9.***.***-K'
      - '12345678-5'   -> '12.***.***-5'
    """
    if not rut:
        return "***"
    cleaned = clean_rut(rut)
    if len(cleaned) < 4:
        return "***"
        
    body = cleaned[:-1]
    dv = cleaned[-1]
    
    if len(body) <= 6:
        return f"{body[0]}***-{dv}"
    elif len(body) == 7:
        return f"{body[0]}.***.***-{dv}"
    else:
        return f"{body[:2]}.***.***-{dv}"
