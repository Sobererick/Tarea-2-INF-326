# ¿Qué acortador elegiríamos para la USM?

## Opción 1 · Medir el alcance de una campaña

Si la USM difunde un magíster por correo y por Instagram, elegiríamos la primera arquitectura. Crearíamos un enlace corto para cada canal, aunque ambos lleven a la misma página. Con el `302` y la instrucción `no-store`, el navegador vuelve al acortador en cada apertura. Antes de redirigir, el acortador espera que el servicio gRPC guarde la hora y la URL corta visitada. Así podemos comparar cuántas solicitudes generó cada canal. Si una persona abre el correo dos veces y usa el enlace en ambas ocasiones, cuenta dos veces.

**Al elegir la opción 1 perdemos rapidez y disponibilidad.** El postulante que abre el enlace por segunda vez tiene que volver a contactar al acortador y esperar otra escritura. Además, si el servicio de registro falla o tarda más de 500 milisegundos en confirmar, el acortador responde con `503`, incluso si la página del magíster funciona. Para comparar los canales de difusión aceptaríamos ese costo. Para un trámite que está a punto de cerrar, hacer depender el acceso de un registro de visitas sería más difícil de justificar.

## Opción 2 · Abrir el calendario desde un QR

Para el QR impreso de una feria de admisión elegiríamos la segunda arquitectura. Si un estudiante abre el calendario al llegar y vuelve a escanear el QR dos minutos después, su navegador puede reutilizar el `301` durante cinco minutos e ir directo al destino. Si otro teléfono pide el mismo enlace, Litestar también puede responder desde su propia caché durante un minuto y ahorrarse la lectura de SQLite. Para quien está en la feria, poder volver al calendario rápidamente vale más que contar cada escaneo.

**Al elegir la opción 2 perdemos visibilidad sobre las visitas y la posibilidad de aplicar de inmediato una corrección del destino.** El segundo escaneo puede ocurrir sin que la USM lo vea. Si se corrige la dirección asociada al QR, un teléfono que ya guardó la anterior puede seguir usándola hasta que venza su copia. Por eso imprimiríamos un QR que apunte a una dirección estable, donde la USM pueda actualizar las fechas sin cambiar el enlace.

La protección frente a ráfagas también tiene un costo. La v2 admite 60 solicitudes por minuto por IP. Si varios estudiantes comparten el wifi de la feria y juntos agotan esa cuota, el siguiente puede recibir un `429` en su primer intento.

## Bonus · Identificadores únicos

Si dos servidores atendieran el mismo dominio con contadores independientes, ambos podrían asignar el código `eRgfR` a destinos distintos. Usaríamos un contador compartido en una base replicada. Cada alta reservaría el siguiente ID y guardaría su equivalencia en una sola transacción, con una restricción de unicidad sobre el código Base62. El enlace se entregaría cuando una mayoría confirmara la escritura. Con eso ganamos unicidad, pero un servidor aislado de la mayoría pierde temporalmente la capacidad de crear enlaces. Para un QR que irá a imprenta, aceptaríamos esa espera.
