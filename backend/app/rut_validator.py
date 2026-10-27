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
