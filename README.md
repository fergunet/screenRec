# ScreenRec

Botón flotante (siempre visible) que guarda un vídeo con los **últimos X segundos** de toda la pantalla.
Funciona en **Linux (X11)** y **Windows 10/11**.

## Uso

| Sistema | Cómo lanzarlo |
|---|---|
| Linux   | `./run.sh` |
| Windows | Doble clic en `run.bat` (necesita Python 3 de [python.org](https://www.python.org/downloads/), con Tkinter, que viene por defecto) |

La primera vez se crea un entorno virtual `.venv` y se instala ffmpeg (paquete `imageio-ffmpeg`); no hace falta
instalar ffmpeg a mano.

- Pulsa **⏺ GUARDAR** (o `F9` con la ventana enfocada) → se guarda `~/Videos/ScreenRec/clip_AAAAMMDD_HHMMSS.mp4`
  (en Windows: `C:\Users\<usuario>\Videos\ScreenRec\`).
- Ajusta X en el selector "Últimos ___ s" (1–30 s; el búfer guarda como máximo 30 s).
- Cierra la ventana para detener la grabación.

## Configuración (variables de entorno)

| Variable | Valores | Por defecto |
|---|---|---|
| `SCREENREC_DIR` | Carpeta donde se guardan los clips | `~/Videos/ScreenRec` |
| `SCREENREC_CAPTURE` | Sólo Windows: `gdigrab` (todos los monitores) o `ddagrab` (Desktop Duplication: menos CPU y mejor con vídeo acelerado por GPU, pero un único monitor) | `gdigrab` |
| `SCREENREC_MONITOR` | Sólo con `ddagrab`: índice del monitor (0, 1, …) | `0` |

## Windows: modo de captura eficiente (`ddagrab`)

Por defecto, en Windows se usa `gdigrab`, que graba **todos los monitores** pero copia cada fotograma de la pantalla
con la CPU. A resoluciones altas (1440p, 4K) o con varios monitores puede:

- consumir mucha CPU y ralentizar el equipo,
- no llegar a 30 fps (el vídeo se ve a saltos),
- mostrar en negro o con parpadeos algunos vídeos que se reproducen con aceleración por GPU
  (navegadores, VLC, Teams/Zoom, juegos).

Si te pasa algo de esto, usa el modo **`ddagrab`** (Desktop Duplication API de Windows 8+): la tarjeta gráfica
entrega directamente la imagen ya compuesta, así que gasta mucha menos CPU y captura mejor el vídeo acelerado por
GPU. Su única limitación es que graba **un solo monitor**, elegido con `SCREENREC_MONITOR` (0 = principal, 1 = el
segundo, …).

Para probarlo una vez, en una ventana de **cmd** dentro de la carpeta del proyecto:

```bat
set "SCREENREC_CAPTURE=ddagrab" && set "SCREENREC_MONITOR=0" && run.bat
```

En **PowerShell**:

```powershell
$env:SCREENREC_CAPTURE = "ddagrab"; $env:SCREENREC_MONITOR = "0"; .\run.bat
```

Para dejarlo fijo (afecta a las ventanas que se abran a partir de ese momento, incluido el doble clic en `run.bat`):

```bat
setx SCREENREC_CAPTURE ddagrab
setx SCREENREC_MONITOR 0
```

Para volver al modo por defecto: `setx SCREENREC_CAPTURE gdigrab`.

## Cómo funciona

ffmpeg graba la pantalla continuamente (`x11grab` en Linux, `gdigrab`/`ddagrab` en Windows) en segmentos H.264 de
1 s dentro de un búfer circular (en RAM en Linux, en `%TEMP%` en Windows; 30 s como máximo, unos 10–30 MB). Al pulsar,
se concatenan los segmentos recientes sin recodificar (instantáneo) y se recortan al final. Por el corte en
fotograma clave, el clip puede durar hasta ~1 s más de lo pedido.

Los errores se guardan en `screenrec.log` dentro de la carpeta de salida.

## Limitaciones

- Linux: sólo sesiones **X11** (no Wayland).
- Windows: el contenido con DRM (Netflix, Disney+, etc. en Edge/Chrome) suele salir en negro; lo bloquea el sistema.
- El propio botón aparece en la grabación. No se graba audio.
