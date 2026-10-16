# Instagram Scraper — adaptación local

Herramienta de línea de comandos en Python para exportar a archivos locales los datos de un perfil de Instagram que sean visibles para el scraper. Guarda los resultados en JSON y, cuando Instagram entrega enlaces descargables, guarda fotos y videos en el disco.

Esta adaptación ejecuta `main.py`; no levanta el servidor REST del proyecto original ni requiere una clave de Meta Graph API o RapidAPI. Consulta endpoints web de Instagram. La sesión local se configura mediante cookies para las consultas que las usan; el feed de publicaciones de perfiles públicos se consulta sin adjuntar cookies cuando la petición autenticada es rechazada.

## Funciones

- Obtiene información básica del perfil.
- Recorre las páginas disponibles de publicaciones y descarga sus medios.
- Intenta obtener reels, seguidores, seguidos, destacados y comentarios.
- Guarda el estado de cada colección (`complete`, `partial` o `failed`) en sus archivos JSON.

La disponibilidad depende de la visibilidad del perfil y de las respuestas de Instagram. El programa no garantiza que Instagram entregue todas las publicaciones, comentarios, reels o relaciones.

## Requisitos

- Python 3.10 o superior.
- Una conexión a Internet.
- Cookies de una sesión propia de Instagram para ejecutar el flujo actual.

## Instalación

```bash
git clone https://github.com/tu-usuario/tu-repositorio.git
cd tu-repositorio
python -m venv .venv
```

Activa el entorno virtual:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install -r requirements.txt
```

## Configurar las cookies

En la raíz del proyecto, crea o edita `instagram_cookies.py` y coloca el encabezado Cookie de tu propia sesión:

```python
INSTAGRAM_COOKIES = "sessionid=TU_SESSIONID; csrftoken=TU_CSRFTOKEN; ds_user_id=TU_ID"
```

Reemplaza los valores de ejemplo por los tuyos. **No publiques ni compartas las cookies.** El archivo `instagram_cookies.py` está incluido en `.gitignore`; revisa que siga ignorado antes de subir cambios a GitHub. Si alguna vez publicaste una cookie, cierra esa sesión de Instagram y genera una nueva.

## Elegir el perfil y ejecutar

En `main.py`, cambia `TARGET_USERNAME` por el nombre de usuario que quieras consultar:

```python
TARGET_USERNAME = "nombre.del.perfil"
```

Ejecuta el scraper desde la raíz del proyecto:

```bash
python main.py
```

El programa no inicia un servidor local ni una API HTTP.

## Archivos generados

Los archivos se guardan bajo `output/`, una carpeta ignorada por Git:

```text
output/
├── profile_<usuario>.json
├── posts_<usuario>.json
├── reels_<usuario>.json
├── followers_<usuario>.json
├── following_<usuario>.json
├── highlights_<usuario>.json
├── comments_<usuario>.json
├── summary_<usuario>.json
└── media/<usuario>/
    ├── posts/
    ├── reels/
    └── highlights/
```

`summary_<usuario>.json` resume cuántos elementos se recopilaron y si cada colección terminó por completo. Los archivos JSON pueden incluir el motivo de una recopilación parcial o fallida.

## Atribución y licencia

Este proyecto adapta código del repositorio [instagram-scraper de `omkarcloud`](https://github.com/omkarcloud/instagram-scraper). La licencia del proyecto original identifica a Chetan Jain como titular del aviso de copyright. Se conserva el aviso y el texto de la licencia MIT en [`LICENSE`](LICENSE); consulta también la [licencia original](https://github.com/omkarcloud/instagram-scraper/blob/master/LICENSE).

Esta versión modifica el flujo para ejecutar una descarga local con `main.py`, guardar resultados y medios en `output/` y configurar una sesión local mediante cookies. Los créditos y avisos de licencia del código original deben conservarse al redistribuir el proyecto.

## Uso responsable

Usa el scraper únicamente con datos a los que tengas autorización para acceder. Respeta la privacidad de las personas, las condiciones de Instagram y la legislación aplicable. Instagram puede cambiar sus endpoints, limitar solicitudes o no devolver algunos datos.
<img width="622" height="325" alt="image" src="https://github.com/user-attachments/assets/14ee0368-3f37-4059-ae63-8af534621144" />
