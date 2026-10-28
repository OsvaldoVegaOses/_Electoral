# H3 — Adaptador de laboratorio y contrato ejecutado

Fecha: 2026-10-28. **Resultado: GO del prototipo experimental**, posterior a las dos elecciones completas/verificadas de H2. ADR-001 PROPUESTO. No se modifica el backend/frontend de TheoGen ni se aprueba un motor productivo.

## Comportamiento entregado

`poc/belenios-3.3.0/adapter/lab_adapter.py` implementa dos operaciones locales:

1. `provision-synthetic`: verifica Belenios 3.3.0/API 6, autentica al administrador dummy de este laboratorio y crea un borrador con preguntas y diez unidades `adapterNN@ejemplo.test`. Comprueba `If-Match` en creación/edición/padrón y coteja la lista leída. Reserva un checkpoint antes del envío y, al confirmar creación, persiste `poc-ID → Belenios UUID`; bloquea repetir creación si ya existe cualquiera de los dos. Una respuesta perdida deja la reserva para reconciliación manual. Un fallo de transporte tras mutación tiene resultado desconocido y **no se reintenta**.
2. `verified-evidence`: exige Tallied, cabeza final, objeto de resultado y SHA-256 del archivo coincidentes con un anclaje local aprobado. Descarga solo datos públicos, verifica hash de objeto y concordancia API/archivo, y ejecuta `belenios-tool` sin red con montaje público de solo lectura. Solo entonces devuelve cifras, participación y referencias de evidencia vinculadas al ID sintético TheoGen.

No usa `archive.zip` administrativo, privadas, semillas, RUT, `Vote.voter_id`, `candidate_id`, `token_votacion`, sesiones o bases de TheoGen. Los tokens del login administrativo se envían como Bearer y permanecen en memoria; no se incluyen en argumentos ni mensajes de error. Solo se admiten `http://127.0.0.1:18001/18002` e IDs `poc-*`.

El anclaje es una entrada de confianza externa al servidor; en esta prueba es `h2-resultados.json`, obtenido y revisado durante H2. Un diseño real necesita firma/custodia independiente de ese anclaje. La etiqueta de imagen no es la raíz de confianza: el adaptador usa el identificador inmutable registrado por H1 y coteja el commit del verificador.

## Validación funcional

Comando: `python tests/check_adapter.py`. [Ocho comprobaciones satisfactorias y exportaciones observadas](evidencias/h3-resultados.json):

- Exportación de A: 5/5, 10 boletas, 10 habilitados, participación 1.0 y verificación exit 0.
- Exportación de B: 6/4 con los mismos denominadores y verificación exit 0.
- Rechazo de anclaje final incorrecto en ambas elecciones.
- Crear/editar borrador, cargar y cotejar diez unidades ficticias con If-Match.
- Rechazo de creación repetida a partir del mapping existente.
- Rechazo de borrador sin escrutinio como resultado final.
- Rechazo de servidor público/destino ajeno al laboratorio.

Son ocho porque las exportaciones y anclajes se ejercitan por separado en A y B. En reanudaciones, el test coteja el borrador ya confirmado en lugar de volver a crearlo. No se agregan boletas a las elecciones cerradas al repetir verificaciones de lectura.

Además, `python tests/check_adapter_failures.py` ejecuta dos fallos controlados sin red ni elecciones nuevas: pérdida de respuesta tras creación conserva el checkpoint y bloquea un segundo envío; una respuesta HTTP incompleta se clasifica como mutación desconocida, sin reintento.

## Esquema de salida y límites

`theogen-belenios-lab-evidence/v1` incluye ID sintético, UUID, versión/commit, conteos, habilitados, votos computados, participación, hash de archivo/evento/resultado, imagen y exit code del verificador. Es un esquema técnico experimental para un futuro expediente; no es un acta firmada ni acredita quórum, estatutos, representación familiar o legalidad de la elección.

Se limita a una pregunta homomórfica de dos opciones y peso 1. No automatiza credenciales/trustees ni adopta claves privadas; esas ceremonias siguen separadas. No implementa OIDC passthrough, recuperación de credenciales, blanco/nulo, ponderación, política familiar ni activación de un proceso productivo. Las transiciones completas se probaron en H2; el adaptador no pretende cubrir toda la API de H0.

**Pendientes fuera del prototipo:** H4 de compatibilidad chilena, reglas familiares y de revoto por institución, evaluación jurídica AGPL/estatutos, operadores y auditor humanos independientes, tratamiento de metadatos, todas las fallas/combinaciones pendientes, endurecimiento/reproducibilidad de dependencias y los gates G2–G4. G1 aprobado no se convierte en aprobación de esos gates.
