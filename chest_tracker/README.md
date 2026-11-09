# Chest Tracker

Cuenta cuántas veces abres cofres (`Chest opens`) y cuántas los rompes (`Chest breaks`).
Solo lee píxeles de la pantalla: detecta una imagen recortada del juego y suma +1 cada vez que aparece.
No lee memoria del juego ni toca el proceso de Fortnite.

Salida en vivo: `counts/counts.txt` (para una fuente de texto en OBS) y `counts/counts.json`.

## Instalar (en el PC donde corre Fortnite)

```bash
pip install mss opencv-python numpy
```

Pon Fortnite en **modo ventana sin bordes** (borderless). En pantalla completa exclusiva la captura sale negra.

## Paso a paso

1. **Saca una captura de la zona de scan**
   ```bash
   python chest_tracker.py snapshot
   ```
   Se guarda en `templates/region.png`. Si el aviso de cofre sale en otra parte de la pantalla, cambia `region` en `config.json` (`[left, top, width, height]`) y repite.

2. **Recorta las plantillas** (lo más fácil: `setup_templates.bat` en Windows, o aquí):
   ```bash
   python chest_tracker.py select templates/region.png templates/chest_open.png
   python chest_tracker.py select templates/region.png templates/chest_break.png
   ```
   Se abre la captura: arrastra el recuadro sobre el aviso y pulsa ENTER.

   Alternativa con coordenadas. Recorta la plantilla de "abrir cofre"** (abre un cofre con la captura del aviso o del icono que aparece) y luego la de "romper cofre":
   ```bash
   python chest_tracker.py crop templates/region.png X Y W H templates/chest_open.png
   python chest_tracker.py crop templates/region.png X Y W H templates/chest_break.png
   ```
   `X Y W H` son píxeles dentro de `region.png`. Recorta un trozo pequeño y muy distintivo del aviso (texto o icono), sin fondo que cambie.

3. **Comprueba que detecta bien**, con una captura donde sale el evento:
   ```bash
   python chest_tracker.py check templates/region.png
   ```
   Verás el `score` de cada plantilla. Un evento debe dar `MATCH` (≥ `threshold`, por defecto 0.85) y lo demás `no match`. Si hay falsos positivos sube `threshold`; si no detecta, bájalo o recorta mejor.

4. **Corre el contador** (grabación continua de la pantalla hasta que cierres la ventana)
   ```bash
   python chest_tracker.py run
   ```
   En Windows basta con doble clic en `run.bat`.
   Cada evento imprime algo como `+1 Chest opens -> 1`. Ctrl+C para parar.

5. **Pon el contador en OBS**: añade una fuente *Texto (GDI+)* o *Texto* y marca *Leer desde archivo* apuntando a `chest_tracker/counts/counts.txt`.

Para empezar de cero: `python chest_tracker.py reset`.

## Archivos

| Archivo | Qué hace |
|---|---|
| `chest_tracker.py` | Captura, detección, contadores y comandos (`run`, `snapshot`, `select`, `crop`, `check`, `reset`) |
| `run.bat`, `setup_templates.bat` | Atajos de Windows para contar y para crear plantillas |
| `config.json` | Zona de scan, fps, umbral, cooldown, rutas de plantillas |
| `templates/` | Plantillas recortadas (no se suben al repo, ver `.gitignore`) |
| `counts/` | Contadores en vivo |
| `tests/test_chest_tracker.py` | Pruebas unitarias de la lógica de detección |

## Cómo funciona

- Cada 1/`fps` s se captura la zona y se compara con cada plantilla (correlación normalizada).
- Un evento cuenta **una vez** cuando la plantilla aparece. No vuelve a contar mientras siga visible.
- `cooldown_seconds` evita contar dos veces el mismo evento si el aviso parpadea.
- Los contadores se guardan al instante y se reanudan si reinicias `run`.

## Pruebas

```bash
python -m unittest discover -s chest_tracker/tests -v
```
