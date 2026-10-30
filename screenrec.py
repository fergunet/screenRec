#!/usr/bin/env python3
"""ScreenRec: graba continuamente la pantalla en un búfer circular y, al pulsar
el botón, guarda en un MP4 los últimos X segundos.

Funcionamiento:
  * ffmpeg captura toda la pantalla (x11grab en Linux/X11, gdigrab o ddagrab en
    Windows) y escribe segmentos MPEG-TS de SEG_SECONDS segundos en un directorio
    temporal (en RAM si existe /dev/shm), sobrescribiéndolos de forma circular
    (segment_wrap).
  * Al pulsar el botón se toman los segmentos más recientes (incluido el que se
    está escribiendo), se concatenan sin recodificar y se recorta el final a los
    últimos X segundos.
"""

import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

IS_WINDOWS = sys.platform == "win32"

SEG_SECONDS = 1
DEFAULT_SECONDS = 30
MAX_SECONDS = 30
DEFAULT_FPS = 30
OUTPUT_DIR = Path(os.environ.get("SCREENREC_DIR", Path.home() / "Videos" / "ScreenRec"))
# Windows: "gdigrab" (todos los monitores, por defecto) o "ddagrab" (Desktop
# Duplication: más eficiente, pero sólo un monitor, SCREENREC_MONITOR=0,1,…)
CAPTURE = os.environ.get("SCREENREC_CAPTURE", "gdigrab").strip().lower()
MONITOR = int(os.environ.get("SCREENREC_MONITOR", "0"))

# Evita que se abra una consola por cada ffmpeg en Windows
POPEN_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("No se encuentra ffmpeg. Instálalo o ejecuta: pip install imageio-ffmpeg")


def log_error(msg):
    """Muestra el error y lo guarda en OUTPUT_DIR/screenrec.log (con pythonw no hay consola)."""
    print(msg, file=sys.stderr)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_DIR / "screenrec.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except OSError:
        pass


def enable_dpi_awareness():
    """En Windows con escalado (125 %, 150 %…) hace que las coordenadas y
    tamaños sean píxeles reales y que la ventana no se vea borrosa."""
    if not IS_WINDOWS:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def capture_input_args(fps, width, height):
    """Argumentos de entrada de ffmpeg según la plataforma."""
    if IS_WINDOWS:
        if CAPTURE == "ddagrab":
            return ["-f", "lavfi", "-i",
                    f"ddagrab=output_idx={MONITOR}:framerate={fps}:draw_mouse=1,"
                    "hwdownload,format=bgra"]
        return ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1", "-i", "desktop"]
    display = os.environ.get("DISPLAY", ":0")
    return ["-f", "x11grab", "-framerate", str(fps), "-draw_mouse", "1",
            "-video_size", f"{width}x{height}", "-i", f"{display}+0,0"]


class Recorder:
    """Proceso ffmpeg que mantiene un búfer circular de segmentos."""

    def __init__(self, ffmpeg, width, height, fps, max_seconds):
        self.ffmpeg = ffmpeg
        self.width, self.height, self.fps = width, height, fps
        self.wrap = math.ceil(max_seconds / SEG_SECONDS) + 3
        base = "/dev/shm" if os.path.isdir("/dev/shm") else None
        self.buffer_dir = Path(tempfile.mkdtemp(prefix="screenrec_", dir=base))
        self.log_path = self.buffer_dir / "ffmpeg.log"
        self.log = None
        self.proc = None
        self.started_at = None

    def start(self):
        cmd = [
            self.ffmpeg, "-hide_banner", "-loglevel", "error",
            *capture_input_args(self.fps, self.width, self.height),
            # libx264 con yuv420p exige dimensiones pares
            "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-force_key_frames", f"expr:gte(t,n_forced*{SEG_SECONDS})",
            "-f", "segment", "-segment_time", str(SEG_SECONDS),
            "-segment_format", "mpegts", "-segment_wrap", str(self.wrap),
            str(self.buffer_dir / "seg%04d.ts"),
        ]
        self.log = open(self.log_path, "wb")
        # stdin se usa para pedirle a ffmpeg que pare ("q"), válido en Linux y Windows
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=self.log, **POPEN_FLAGS)
        self.started_at = time.monotonic()

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def error_output(self):
        try:
            return self.log_path.read_text(errors="replace").strip()
        except OSError:
            return ""

    def buffered_seconds(self):
        if not self.started_at:
            return 0
        return min(time.monotonic() - self.started_at, self.wrap * SEG_SECONDS)

    def save_clip(self, seconds, out_path):
        """Concatena los segmentos recientes y guarda los últimos `seconds` s."""
        segs = sorted(self.buffer_dir.glob("seg*.ts"), key=lambda p: p.stat().st_mtime)
        if not segs:
            raise RuntimeError("El búfer aún está vacío")
        # +1 por el segmento en curso (parcial)
        segs = segs[-(math.ceil(seconds / SEG_SECONDS) + 1):]

        # Se copian a otro sitio para que ffmpeg no los sobrescriba mientras leemos
        with tempfile.TemporaryDirectory(dir=self.buffer_dir.parent) as tmp:
            joined = Path(tmp) / "joined.ts"
            with open(joined, "wb") as dst:
                for s in segs:
                    try:
                        with open(s, "rb") as src:
                            shutil.copyfileobj(src, dst)
                    except OSError:
                        pass
            cmd = [
                self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-sseof", f"-{seconds}", "-i", str(joined),
                "-c", "copy", "-movflags", "+faststart", str(out_path),
            ]
            res = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, **POPEN_FLAGS)
            if res.returncode != 0 or not out_path.exists():
                raise RuntimeError(res.stderr.decode(errors="replace").strip() or "ffmpeg falló")

    def stop(self):
        if self.alive():
            try:
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait()
        if self.log:
            self.log.close()
        shutil.rmtree(self.buffer_dir, ignore_errors=True)


class App:
    def __init__(self, root):
        self.root = root
        self.ffmpeg = find_ffmpeg()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        self.recorder = Recorder(self.ffmpeg, w - w % 2, h - h % 2, DEFAULT_FPS, MAX_SECONDS)
        self.saving = False
        self.closing = False

        root.title("ScreenRec")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        frame = ttk.Frame(root, padding=6)
        frame.pack()

        self.button = tk.Button(
            frame, text="⏺  GUARDAR", font=("Segoe UI" if IS_WINDOWS else "Sans", 14, "bold"),
            bg="#d32f2f", fg="white", activebackground="#b71c1c", activeforeground="white",
            relief="raised", padx=12, pady=6, command=self.save,
        )
        self.button.grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(frame, text="Últimos").grid(row=1, column=0, pady=(6, 0))
        self.seconds = tk.IntVar(value=DEFAULT_SECONDS)
        ttk.Spinbox(frame, from_=1, to=MAX_SECONDS, width=5, textvariable=self.seconds).grid(
            row=1, column=1, pady=(6, 0))
        ttk.Label(frame, text="s").grid(row=1, column=2, pady=(6, 0), sticky="w")

        self.status = ttk.Label(frame, text="Iniciando…", width=26, anchor="center")
        self.status.grid(row=2, column=0, columnspan=3, pady=(4, 0))

        root.bind("<F9>", lambda e: self.save())

        # Esquina superior derecha por defecto
        root.update_idletasks()
        root.geometry(f"+{w - root.winfo_width() - 20}+60")

        self.recorder.start()
        self.root.after(1000, self.tick)

    def tick(self):
        if self.closing:
            return
        # Windows puede quitar el "siempre encima" al cambiar de ventana a pantalla completa
        self.root.attributes("-topmost", True)
        if not self.recorder.alive():
            err = self.recorder.error_output()
            self.status.config(text="ffmpeg se detuvo (screenrec.log)")
            log_error("ffmpeg terminó:\n" + err)
            return
        if not self.saving:
            self.status.config(text=f"● Búfer: {int(self.recorder.buffered_seconds())} s")
        self.root.after(1000, self.tick)

    def get_seconds(self):
        try:
            return max(1, min(MAX_SECONDS, int(self.seconds.get())))
        except (tk.TclError, ValueError):
            return DEFAULT_SECONDS

    def save(self):
        if self.saving:
            return
        self.saving = True
        seconds = self.get_seconds()
        self.button.config(state="disabled")
        self.status.config(text="Guardando…")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / f"clip_{datetime.now():%Y%m%d_%H%M%S}.mp4"

        def work():
            # Pequeña espera para que el segmento en curso incluya el instante de la pulsación
            time.sleep(0.3)
            try:
                self.recorder.save_clip(seconds, out)
                msg, ok = f"✔ {out.name}", True
            except Exception as e:  # noqa: BLE001
                msg, ok = "✖ Error al guardar", False
                log_error(f"Error guardando clip: {e}")
            self.root.after(0, self.done, msg, ok, out)

        threading.Thread(target=work, daemon=True).start()

    def done(self, msg, ok, out):
        if self.closing:
            return
        self.status.config(text=msg)
        if ok:
            print(f"Clip guardado: {out}")
        self.button.config(state="normal")
        self.root.after(2500, lambda: setattr(self, "saving", False))

    def quit(self):
        if self.closing:
            return
        self.closing = True
        self.recorder.stop()
        self.root.destroy()


def main():
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print("Aviso: sesión Wayland detectada; x11grab sólo funciona en sesiones X11.", file=sys.stderr)
    enable_dpi_awareness()
    root = tk.Tk()
    app = App(root)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: app.quit())
    root.mainloop()


if __name__ == "__main__":
    main()
