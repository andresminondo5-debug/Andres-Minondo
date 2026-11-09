# Pirate Shop Chest Tracker PRO

App de escritorio para Windows 10/11 que cuenta **cofres abiertos** y **cofres destruidos** en Fortnite
(Pirate Shop) usando solo lo que aparece en tu pantalla. Tiene ventana con contadores, overlay transparente,
estadísticas guardadas en tu PC y un instalador.

## Lo que hace y lo que NO hace

- Captura tu pantalla y compara imágenes (OpenCV). Cada evento cuenta **una vez**; un aviso que sigue visible no suma más.
- Cuenta abiertos y destruidos con **plantillas distintas**, así que no los mezcla.
- **No lee la memoria de Fortnite**, no inyecta código, no toca archivos del juego y no envía teclas ni clics.
- **No cuenta nada sin calibrar.** Si no hay plantillas, el contador se queda en 0 y la app lo avisa.
- **El detector todavía no está validado con cofres reales.** Eso solo se sabe cuando lo pruebes con tus propias
  capturas o videos. Hasta entonces la app muestra un aviso y no afirma que reconoce los cofres de Pirate Shop.

## Instalar (usuario final)

1. Ejecuta `PirateShopTrackerSetup.exe` (no pide permisos de administrador).
2. Marca el acceso directo del escritorio y abre la app.
3. Si Windows SmartScreen avisa "aplicación no reconocida": **Más información → Ejecutar de todos modos**.
   Es normal en apps sin firma digital.

## Calibrar el detector (una vez)

1. Pon Fortnite en **ventana sin bordes** (en pantalla completa exclusiva la captura sale negra).
2. Abre la app → **Calibrar detector**.
3. **Captura de pantalla** con el aviso de cofre visible, o **Abrir imagen o video** con una grabación.
4. Arrastra un recuadro pequeño y muy distintivo sobre el aviso (texto o icono). Guárdalo como
   **ABIERTO** o **DESTRUIDO**. Repite para ambos.
5. **Probar en esta imagen** con una captura donde se vea el evento: debe decir `COINCIDE` en el tipo correcto.
6. **Escanear video completo** con una grabación con varios cofres. Compara los tiempos con el video.
7. Si acertó en tus pruebas, marca **"Confirmo que el detector acertó…"**. Así el aviso amarillo desaparece.

Consejos: si da falsos positivos, sube el umbral en `settings.json` (`threshold`, por defecto 0.85).
Si no detecta, recorta mejor la plantilla o calibra con capturas a la misma resolución que juegas.

## Uso diario

- Al abrir la app: carga configuración, busca `FortniteClient-Win64-Shipping.exe` y, si está calibrado y habilitado,
  inicia el seguimiento solo.
- Mientras Fortnite está abierto graba la pantalla y guarda cada evento al instante en la base local.
- **Overlay**: botón *Mostrar overlay*. Arrástralo, cambia su tamaño desde la esquina y ciérralo con la ×.
- **Estadísticas**: pestañas *Resumen* (hoy, histórico, cofres por hora), *Sesiones* y *Gráfica* de 14 días.

## Dónde se guardan los datos

`%APPDATA%\PirateShopTracker\`
- `tracker.db`: sesiones y eventos (SQLite).
- `settings.json`: ajustes.
- `templates\`: las plantillas de calibración.

## Compilar el instalador (Windows)

Necesitas una vez: **Python 3.10 o superior** (marca "Add python.exe to PATH") y, para el instalador,
**Inno Setup 6** (https://jrsoftware.org/isdl.php).

1. Descomprime el proyecto.
2. Haz doble clic en **`build\build.bat`**. Instala librerías, corre las pruebas, empaqueta con PyInstaller
   y, si está Inno Setup, genera `installer_output\PirateShopTrackerSetup.exe`.
3. Ese `.exe` es el que instalas en cualquier PC.

Para ejecutar sin instalar: `python run_app.py`.

## Limitaciones honestas

- Solo Windows. Las pruebas automáticas corren en cualquier sistema, pero la captura y el instalador son de Windows.
- La detección depende de la **resolución y escala** del juego. Calibra con la misma configuración que usas.
- Un aviso muy parecido a otro, o con fondo que cambia, puede dar falsos positivos o fallos. Eso se ajusta con las plantillas.
- Los atajos globales de teclado no están incluidos; el overlay se controla con el ratón.
- No hay icono propio todavía: se puede añadir un `.ico` y ponerlo en `build.bat` con `--icon`.

## Estructura

| Ruta | Qué hay |
|---|---|
| `run_app.py` | Entrada de la app |
| `app/config.py` | Ajustes, carpetas, proceso de Fortnite |
| `app/detector.py` | Plantillas, detección con histéresis y cooldown, escaneo de video |
| `app/engine.py` | Hilo de captura y conteo; guarda cada evento |
| `app/storage.py` | Base SQLite local: sesiones, eventos, estadísticas |
| `app/ui/` | Tema oscuro, ventana principal, overlay, calibración |
| `tests/test_core.py` | 10 pruebas de almacenamiento, detector, motor y video |
| `build/build.bat` | Compilación de un solo clic (Windows) |
| `build/installer.iss` | Script del instalador (Inno Setup) |

## Pruebas

```bash
python -m unittest discover -s tests -v
```
