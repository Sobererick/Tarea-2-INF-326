# Tarea 2 - INF326: acortador de URLs

Dos versiones de un acortador en Litestar. La primera registra visitas mediante gRPC. La segunda usa caché y limita las solicitudes por IP. Ambas guardan las equivalencias en SQLite y atienden por HTTPS.

## Integrantes

| Nombre | Rol USM |
| --- | --- |
| Erick Avila | 202273103-6 |
| Emilio Valdebenito | 202273040-4 |
| Hans Villouta | 202273052-8 |

## Ejecución

Se necesita Docker con Compose v2, contenedores Linux y los puertos 8443 y 8444 libres. La primera ejecución requiere internet. Desde la carpeta que contiene `compose.yaml`, ejecutar el siguiente comando.

```sh
docker compose up --build -d
```

El certificado local se genera automáticamente. Para probar ambas versiones, reemplazar la dirección entre comillas por una URL completa que empiece con `https://` o `http://`. Si se omite, la demo usa la página de admisión de la USM.

```sh
docker compose exec v1 python demo.py "https://es.wikipedia.org/wiki/Chile"
docker compose exec v1 python demo.py "https://example.org/"
docker compose exec v2 python demo.py "https://es.wikipedia.org/wiki/Chile"
```

Cada demo imprime la `short_url` y la consulta dos veces. El campo `Location` muestra el destino elegido. La v1 devuelve `302` y registra ambas visitas. La v2 devuelve `301`. Para seguir la redirección, abrir la `short_url` en el navegador del equipo donde corre Docker.

## IDs y datos guardados

Con la base de v1 vacía, los dos primeros comandos de la demo muestran estas filas de SQLite:

```text
SQLite → id=597652313  hash=eRgfR  long_url=https://es.wikipedia.org/wiki/Chile
SQLite → id=597652314  hash=eRgfS  long_url=https://example.org/
```

Cada alta aumenta el ID en uno. Antes de leer el último ID, el acortador reserva la escritura en SQLite. Si dos altas llegan juntas, una espera a que la otra termine. El campo `hash` representa el ID en Base62, así que cada ID produce un código distinto. Cada versión lleva su propia secuencia y, al reiniciar, continúa desde el último ID guardado. Abrir un enlace conserva su ID.

Además de los tres campos que muestra la demo, v1 guarda la hora UTC y la URL corta de cada visita en la base del servicio gRPC. En v2, Litestar mantiene en memoria la redirección durante 60 segundos y cuenta las solicitudes para aplicar el límite de 60 por minuto por IP. El navegador puede conservar el destino durante 5 minutos.

Las pruebas se ejecutan con `docker compose exec v1 python -m unittest -v test_shortener`. La prueba de concurrencia crea 20 enlaces y comprueba que sus IDs sean consecutivos y sus códigos distintos. Para detener los servicios y conservar los datos, usar `docker compose down`.
