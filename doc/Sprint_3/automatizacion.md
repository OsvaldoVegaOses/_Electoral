# Desarrollo autonomo del Sprint 3

Autorizado por el titular el 2026-10-30. Usa la sesion ChatGPT ya autenticada de Codex CLI; no crea una clave API ni almacena tokens en Git. Metodo: [ejecucion no interactiva y resultados estructurados con Codex](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex).

## Funcionamiento

Tarea Windows `TheoGen-Electoral-Sprint3-Autonomous`: primer disparo tres horas despues de instalarse; repeticion cada tres horas. Requiere el equipo encendido y la sesion Windows del titular iniciada. No depende de que esta conversacion siga abierta. No se configura ejecucion como SYSTEM ni se guarda una contrasena Windows.

Cada ciclo elige una tarea preparada de `automation/sprint3/queue.json`. Prioridad inicial: politica de simulacion CPA IAC. Maximo cuatro procesos de desarrollo al dia, dos intentos por tarea, 45 minutos por agente y 40 minutos de espera CI por ciclo. Una CI conocida que siga en curso se consulta en el siguiente ciclo, sin enviar otra.

El controlador crea un worktree propio en `.runtime/autonomy/worktrees/`, invoca Codex con sandbox `workspace-write`, revision automatica de permisos y resultado JSON, y permite cambios solo en las rutas declaradas. No usa bypass de sandbox. El escritor no hace commit, push ni merge: el controlador exige codigo funcional y tests nuevos, verifica el alcance, conserva los tests existentes y registra el candidato.

La CI Azure usa el SHA completo y un Git bundle limpio; deben pasar diez controles obligatorios sin omisiones. Se comprueba la identidad del resumen, resultados y manifiesto OCI retenido. Solo entonces se publica el PR tecnico y se integra si main no avanzo durante la validacion. Los cambios pendientes del checkout original nunca se sobrescriben.

La ejecucion es unica mediante bloqueo entre procesos y politica Windows IgnoreNew. Si una mutacion remota queda incierta, se conserva el candidato y el estado `needs_reconciliation`; no se repite automaticamente. Los fallos de lectura de una CI ya identificada solo reanudan su consulta. Agotar intentos deja la tarea bloqueada y conserva su evidencia. Agotar la cola tecnica produce estado ocioso, no aceptacion electoral.

## Limites del mandato

Los ciclos no envian correos, no usan personas reales, no activan Belenios ni cambian la instancia Azure desplegada. La institucion de referencia y sus antecedentes reportados estan en [CPA IAC](caso-cpa-iac.md). No se publican el ZIP, identidades personales, pagos ni datos de estudiantes. La aprobacion de desarrollo no ratifica el Comite ni sustituye G2/G3/G4, una autoridad de credenciales, los custodios o el revisor independiente.

## Operacion

```powershell
.\scripts\run_sprint3_autonomous.ps1 -Action preflight
.\scripts\run_sprint3_autonomous.ps1 -Action status
.\scripts\run_sprint3_autonomous.ps1 -Action pause
.\scripts\run_sprint3_autonomous.ps1 -Action resume
Get-ScheduledTaskInfo -TaskName TheoGen-Electoral-Sprint3-Autonomous
```

`pause` evita nuevos ciclos; no mata una operacion ya aceptada. Para revisar una incertidumbre, cotejar GitHub/Azure de forma solo lectura y los IDs guardados antes de modificar el estado. No borrar el estado, worktrees o evidencia para provocar otra ejecucion. La tarea Windows se instala mediante `scripts/install_sprint3_schedule.ps1` y permite ajustar su intervalo de forma explicita.

Los resultados publicables se sintetizan en PR; el estado detallado queda en `.runtime/autonomy`. Los JSONL privados de Codex no son un informe publico ni una revision independiente. La siguiente iteracion no reanuda un commit ajeno ni toma una respuesta del escritor como prueba de CI.
