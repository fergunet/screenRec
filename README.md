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

- Pulsa **⏺ GUARDAR** (o `F9` con la ventana enfocada) → se guarda `clip_AAAAMMDD_HHMMSS.mp4` en la carpeta de
  salida (por defecto `~/Videos/ScreenRec/`; en Windows `C:\Users\<usuario>\Videos\ScreenRec\`).
- Ajusta X en el selector "Últimos ___ s" (1–30 s; el búfer guarda como máximo 30 s). El valor elegido se recuerda
  para la próxima vez.
- Cierra la ventana para detener la grabación.

## Configuración (`config.ini`)

La configuración se guarda en `config.ini`, junto a `screenrec.py`. Se crea automáticamente con los valores por
defecto la primera vez que se ejecuta la aplicación, y cada opción viene explicada con un comentario dentro del
propio fichero. Edítalo con cualquier editor de texto (Bloc de notas, gedit…) y **reinicia ScreenRec** para aplicar
los cambios.

```ini
[screenrec]
carpeta_salida =
segundos = 30
fps = 30
captura_windows = gdigrab
monitor = 0
```

| Opción | Valores | Por defecto |
|---|---|---|
| `carpeta_salida` | Carpeta donde se guardan los clips. Admite `~` y variables de entorno (`%USERPROFILE%\Desktop`) | vacío = `~/Videos/ScreenRec` |
| `segundos` | Segundos que se guardan al pulsar (1–30). También se cambia desde la ventana | `30` |
| `fps` | Fotogramas por segundo (5–60). Bajarlo (p. ej. a 15) reduce el uso de CPU | `30` |
| `captura_windows` | Sólo Windows: `gdigrab` (todos los monitores) o `ddagrab` (más eficiente, un solo monitor; ver abajo) | `gdigrab` |
| `monitor` | Sólo con `ddagrab`: monitor a grabar (0 = principal, 1 = segundo, …) | `0` |

Si algún valor no es válido se usa el valor por defecto y se anota un aviso en `screenrec.log`. Para volver a la
configuración inicial basta con borrar `config.ini`. El fichero no se sube a git, así que cada equipo tiene el suyo.

> Al cambiar los segundos desde la ventana, `config.ini` se reescribe y se pierden los comentarios que hayas añadido
> tú (los valores se conservan).

## Windows: modo de captura eficiente (`ddagrab`)

Por defecto, en Windows se usa `gdigrab`, que graba **todos los monitores** pero copia cada fotograma de la pantalla
con la CPU. A resoluciones altas (1440p, 4K) o con varios monitores puede:

- consumir mucha CPU y ralentizar el equipo,
- no llegar a 30 fps (el vídeo se ve a saltos),
- mostrar en negro o con parpadeos algunos vídeos que se reproducen con aceleración por GPU
  (navegadores, VLC, Teams/Zoom, juegos).

Si te pasa algo de esto, usa el modo **`ddagrab`** (Desktop Duplication API de Windows 8+): la tarjeta gráfica
entrega directamente la imagen ya compuesta, así que gasta mucha menos CPU y captura mejor el vídeo acelerado por
GPU. Su única limitación es que graba **un solo monitor**.

Para activarlo, edita `config.ini`, cambia estas líneas y reinicia ScreenRec:

```ini
captura_windows = ddagrab
monitor = 0
```

(`monitor = 0` es la pantalla principal; pon `1`, `2`… para grabar otra.) Para volver al modo por defecto, pon
`captura_windows = gdigrab`. Si con `fps = 30` sigue yendo justo, prueba también a bajarlo a `fps = 15`.

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
