# PromiScraper

Bot de Twitter/X que publica automáticamente los partidos del día de la **Liga Profesional Argentina**, scrapeando [promiedos.com.ar](https://www.promiedos.com.ar).

---

## Funcionalidades

- **12:00 ART** — publica un hilo con todos los partidos del día (equipos, hora, jornada).
- **10 minutos antes de cada partido** — publica un tweet de recordatorio individual.
- Si no hay partidos, igual tweetea avisando.
- Modo **DRY RUN** automático si no hay credenciales configuradas (solo loguea, no publica).

---

## Requisitos

- Python 3.10+
- Cuenta de desarrollador en [X Developer Portal](https://developer.x.com) con plan **Basic** o superior (necesario para publicar tweets vía API)
- App configurada con permisos **Read and Write** (OAuth 1.0a)

---

## Instalación

```bash
# 1. Clonar el repo
git clone <url-del-repo>
cd PromiScraper

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
# → editar .env con las credenciales de Twitter
```

---

## Configuración

Editar el archivo `.env`:

```env
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
```

Estos 4 valores se obtienen en el [X Developer Portal](https://developer.x.com/en/portal/projects-and-apps), sección **Keys and tokens** de tu app.

> Si alguno de los 4 está vacío, el bot arranca en **modo DRY RUN** (loguea los tweets pero no los publica).

---

## Uso

| Comando | Descripción |
|---|---|
| `python main.py` | Inicia el servicio continuo (bloquea la consola) |
| `python main.py --ping` | Publica un tweet de prueba al instante para verificar credenciales |
| `python main.py --test` | Simula todos los tweets del día sin publicarlos (DRY RUN) |
| `python main.py --scrape` | Solo muestra los partidos del día por consola y sale |

---

## Estructura del proyecto

```
PromiScraper/
├── main.py            # Entry point y modos de ejecución
├── scheduler.py       # Jobs de APScheduler (resumen diario + recordatorios)
├── scraper.py         # Scraping de promiedos.com.ar
├── formatter.py       # Generación de texto de tweets y hashtags
├── twitter_client.py  # Cliente de Tweepy con soporte DRY RUN
├── config.py          # Configuración central (constantes + clase Config)
├── requirements.txt
├── .env.example
├── run.bat            # Wrapper para Windows (configura UTF-8)
└── logs/
    └── promscraper.log
```

---

## Jobs programados

| Job | Horario | Descripción |
|---|---|---|
| `daily_summary` | Todos los días 12:00 ART | Hilo con los partidos del día |
| `schedule_reminders` | Todos los días 00:05 ART | Lee los partidos y agenda los recordatorios del día nuevo |
| `prematch_<id>` | 10 min antes de cada partido | Tweet de aviso por partido |

Al iniciar, el servicio también ejecuta `schedule_reminders` inmediatamente para cubrir los partidos del día actual.

---

## Formato de tweets

**Resumen diario (12:00 hs):**
```
🏆 Liga Profesional Argentina
📅 Hoy, jueves 12 de marzo

⏰ 19:15 | Talleres de Córdoba vs Instituto
⏰ 19:15 | Estudiantes RC vs Belgrano
⏰ 21:30 | Huracán vs River Plate

#LigaProfesional #Fútbol
```
Si supera 280 caracteres, se publica como hilo numerado.

**Recordatorio (10 min antes):**
```
⚽ ¡Faltan 10 minutos!

🏆 Liga Profesional Argentina
Huracán 🆚 River Plate
⏰ 21:30 hs

#Huracán #RiverPlate #LigaProfesional
```

---

## Logs

Todos los eventos se guardan en `logs/promscraper.log`. Los tweets simulados (DRY RUN) se muestran en un bloque visual en el log:

```
╔════════════════════════════════════════════════════╗
║           [TWEET SIMULADO]  (198 chars)            ║
╠════════════════════════════════════════════════════╣
║                                                    ║
║ ⚽ ¡Faltan 10 minutos!                             ║
║                                                    ║
║ 🏆 Liga Profesional Argentina                      ║
║ Huracán 🆚 River Plate                             ║
║ ⏰ 21:30 hs                                        ║
║                                                    ║
╚════════════════════════════════════════════════════╝
```

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `403 Forbidden - not configured with appropriate oauth1 app permissions` | La app está en modo Read only | Cambiar a **Read and Write** en el portal y regenerar los tokens |
| `402 Payment Required - does not have any credits` | Plan de API insuficiente | Activar plan **Basic** o superior en el X Developer Portal |
| `No se encontró sección de Liga Profesional Argentina` | Cambio de estructura en promiedos.com.ar | Revisar `scraper.py` |

---

## Dependencias

| Paquete | Uso |
|---|---|
| `requests` | HTTP requests al scraper |
| `beautifulsoup4` + `lxml` | Parsing de HTML |
| `pytz` | Timezone America/Argentina/Buenos_Aires |
| `python-dotenv` | Carga de credenciales desde `.env` |
| `apscheduler` | Scheduler de jobs (cron + one-shot) |
| `tweepy` | Cliente de la API de X/Twitter |
