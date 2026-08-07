# Log de ciberseguridad

| Riesgo | Impacto | Medida aplicada |
|---|---|---|
| Acceso no autorizado | Exposición de documentos y decisiones | JWT, contraseñas con Argon2 y control por proyecto |
| Fuga de credenciales Jira/LLM | Compromiso de servicios externos | Variables de entorno; nunca se envían al frontend |
| Prompt injection en documentos | Respuestas manipuladas | El MVP no ejecuta instrucciones de documentos y exige evidencia |
| Relación semántica incorrecta | Decisión errónea | Estado candidato y validación humana |
| Exposición entre proyectos | Acceso lateral | Asociación usuario-proyecto validada en backend |
| Dependencia de terceros | Interrupción | Datos demo y procesamiento determinístico sin LLM |
| Alucinación | Información falsa | Respuesta sin evidencia devuelve “información insuficiente” |
| Modificación automática | Cambios no autorizados | El MVP solo recomienda; no escribe en Jira ni documentos |
