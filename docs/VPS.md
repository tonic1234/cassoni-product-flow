# Instalar el agente en el VPS (worker + cron + panel)

Guía para dejar el agente SEO corriendo solo en un servidor Linux. Todo lo que hace
cada corrida está en `tools/agente_diario.py`; esta guía solo lo instala.

## Qué hace cada corrida

1. Toma las pendientes de `lista.txt` (la arma el SEO, una URL por línea). Si no
   quedan, propone fichas desde Search Console en `lista-propuestas.txt`.
2. Procesa hasta 10 fichas por día (`CASSONI_FICHAS_POR_DIA`), de lunes a viernes de
   9 a 18 (hora del servidor), con pausas al azar entre fichas.
3. Deja el reporte del día en `evidencia/diario/AAAA-MM-DD.json` y `.html`.
4. Regenera el panel de observabilidad en `publico/index.html`.
5. Los lunes mide el efecto de lo escrito a 14 y 28 días.

Correrlo varias veces por día es seguro: el cupo y lo ya hecho viven en
`cassoni_sched.json` (escritura) o `cassoni_sched_seco.json` (en seco).

## 1. Instalar

```bash
# la versión v5 está en la rama flujo-seo-v2 hasta que se mergee a master
cd /opt && git clone -b flujo-seo-v2 https://github.com/tonic1234/cassoni-product-flow cassoni && cd cassoni
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
mkdir -p logs creds evidencia/diario publico
```

Copiar por un canal seguro (no por git, no por chat):

- `.env.prod` → `/opt/cassoni/.env.prod`
- `creds/gsc-service-account.json` → `/opt/cassoni/creds/` (permisos `600`)
- `cassoni.db` (opcional: trae el historial y la caché de volúmenes)

En `.env.prod`, revisar:

```
CASSONI_DFS_PRESUPUESTO_USD=1.50     # con 0.30 la corrida se corta y no hay keywords
CASSONI_MODO_KEYWORDS=reglas         # reglas del SEO (Alex, 17-nov). Es el default
CASSONI_H1_UMBRAL_NOMBRE=1000        # pendiente de confirmar con el SEO
```

## 2. Probar antes del cron

```bash
./venv/bin/python -m cassoni.cli --env prod --preflight      # conexiones, sin gastar LLM
./venv/bin/python -m pytest -q                               # tests
echo "https://cassoni.com/product/mesh-elegant-ceiling-lamp-luceplan/" > lista.txt
./venv/bin/python tools/agente_diario.py --sin-horario       # una corrida en seco
ls evidencia/diario publico
```

## 3. Cron

Usuario sin privilegios, zona horaria del equipo. En seco hasta que el SEO apruebe
el primer lote:

```cron
CRON_TZ=America/Argentina/Buenos_Aires
5 9-17 * * 1-5  cd /opt/cassoni && ./venv/bin/python tools/agente_diario.py >> logs/cron.log 2>&1
```

Cuando el SEO apruebe, agregar `--write` (escribe `name` sin la marca, porque la
tienda agrega «by {Marca}» con el logo, y `description`):

```cron
5 9-17 * * 1-5  cd /opt/cassoni && ./venv/bin/python tools/agente_diario.py --write >> logs/cron.log 2>&1
```

## 4. Panel

`publico/` es estático: se sirve con cualquier servidor web. Tiene datos del
cliente, así que va con usuario y contraseña. Ejemplo con nginx:

```nginx
location /cassoni/ {
    alias /opt/cassoni/publico/;
    auth_basic "Cassoni";
    auth_basic_user_file /etc/nginx/cassoni.htpasswd;
}
```

El panel muestra: si el worker corrió en las últimas 26 h, modo (seco o escritura),
conexiones (Search Console, WooCommerce, LLM, DataForSEO y su saldo), fichas
procesadas y aprobadas, escritas en la tienda, keywords agregadas, costo acumulado y
por ficha, el gráfico de 30 días, la cola, las abandonadas, los errores de los logs,
las últimas fichas con su H1 y keywords, la medición y los reportes diarios.

## Qué mirar si algo falla

| En el panel | Qué hacer |
|---|---|
| «Sin correr hace N h» | `tail logs/cron.log`; revisar el cron y la zona horaria |
| Una conexión en rojo | `--preflight`; credenciales en `.env.prod` |
| Saldo de DataForSEO en amarillo (< US$ 5) | cargar saldo: sin él no hay keywords |
| Fichas «abandonadas» | fallaron 2 veces; el motivo está en la tabla. Revisar con el SEO |
| Alertas «Error» repetidas | el texto dice el paso; ver `logs/agente-AAAA-MM-DD.log` |
