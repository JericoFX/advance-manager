# Guía de uso de la utilidad RS de Advance Manager

## Visión general
La utilidad `rs.py` se centra ahora en un único flujo de trabajo gráfico para examinar y modificar texturas dentro de archivos RS del motor Asura. Al ejecutar el script se abre directamente la interfaz de gestión, que permite navegar por el árbol de recursos, previsualizar las imágenes con Pillow y preparar reemplazos sin recurrir a la línea de comandos.

## Novedades destacadas
- **Interfaz modernizada** con componentes `ttk`, controles estilizados y una disposición idéntica a la versión clásica para mantener la familiaridad.
- **Avisos de formato inteligente**: si el reemplazo no coincide con la compresión (BC/DXT) o el canal alfa esperado, el programa muestra una advertencia antes de continuar.
- **Copias de seguridad opcionales**: la primera vez que importas una textura se te pregunta si deseas crear respaldos automáticos. La preferencia puede cambiarse desde la casilla «Crear respaldo automático».
- **Exportación masiva mejorada**: ahora es posible seleccionar carpetas completas en el árbol y exportar todas las imágenes contenidas en ellas con un solo paso.
- **Arrastrar y soltar**: suelta archivos DDS/PNG/TGA directamente sobre la ventana para importarlos sin pasar por el cuadro de diálogo.
- **Instalación guiada de dependencias**: un nuevo script para Windows automatiza la descarga de Pillow y TkinterDnD2, facilitando la distribución de paquetes.

## Requisitos
- Python 3.10 o superior.
- Tkinter (incluido en la mayoría de distribuciones estándar de Python).
- [Pillow](https://python-pillow.org/) para la previsualización de texturas.
- [TkinterDnD2](https://pypi.org/project/TkinterDnD2/) para habilitar arrastrar y soltar en Windows.

Puedes instalar las dependencias manualmente con:

```bash
python -m pip install -r requirements.txt
```

En Windows también se incluye `scripts/install_windows_dependencies.bat`, que acepta opcionalmente la ruta al intérprete de Python:

```bat
scripts\install_windows_dependencies.bat
scripts\install_windows_dependencies.bat C:\Python311\python.exe
```

## Uso de la interfaz
1. Ejecuta `python rs.py`. Si Tkinter está disponible se abrirá la ventana principal.
2. Pulsa **Open Archive** y elige un archivo `.asr/.pc/.es`. El árbol mostrará todas las texturas detectadas.
3. Selecciona una o varias entradas (o carpetas completas) y usa **Export Selected** para guardarlas. El programa generará ficheros `.rsmeta` que aceleran la importación posterior.
4. Para importar un reemplazo:
   - Selecciona la textura en el árbol y usa **Import Replacement**, o arrastra la imagen directamente sobre la ventana.
   - El gestor comprueba automáticamente el formato. Si detecta diferencias (p. ej. la textura original es BC3/DXT5 con alfa y el reemplazo no), mostrará un aviso detallado.
   - Activa la casilla de respaldo si deseas conservar la textura original en la carpeta `rsmanager_backups` junto al archivo importado.
5. Cuando estés conforme con la cola de reemplazos, genera un parche con **Create Patch** o escribe un archivo completo con **Save Archive As**.
6. El botón **Load Modification Log** permite reimportar un `.replacements.json` generado anteriormente.

## Consejos prácticos
- Usa la barra de búsqueda para filtrar texturas rápidamente; la selección previa se conserva para agilizar el flujo de trabajo.
- Tras arrastrar un archivo, comprueba el mensaje de estado inferior para confirmar que el reemplazo quedó en cola.
- Los respaldos incorporan un sello temporal para evitar sobrescrituras accidentales.
- Si necesitas volver a activar la pregunta de respaldo, desmarca y vuelve a marcar la casilla; la preferencia se aplica inmediatamente.

Con estas mejoras la herramienta ofrece un ciclo de edición más ágil: abre ➜ exporta ➜ modifica ➜ verifica en la GUI ➜ aplica o crea un parche. ¡Disfruta del nuevo gestor de texturas!
