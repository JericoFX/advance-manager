# Guía de uso de la utilidad RS de Advance Manager

## ¿Qué hace el programa?
La utilidad `rs.py` permite trabajar con archivos RS gestionados por el motor Asura. Con ella puedes extraer el contenido de un archivo `.asr/.pc`, modificar texturas y volver a empaquetarlas sin reconstruir el contenedor completo. El script incluye un modo de línea de comandos para extraer, reempacar o generar parches mínimos, y un modo gráfico opcional centrado en texturas.

> **Limitación actual:** tanto el visor gráfico como las herramientas de reemplazo se concentran en entradas de imagen. Otros tipos de recursos se mantienen intactos durante el flujo de trabajo.

## Requisitos previos
- Python 3.10 o superior instalado en tu sistema.
- Tkinter (se incluye con la mayoría de instalaciones de Python en Windows y macOS) para poder abrir la interfaz gráfica.
- Pillow (`pip install Pillow`) para previsualizar las imágenes dentro del visor gráfico.

## Instalación
1. Clona o descarga este repositorio en tu equipo.
2. (Opcional) Crea y activa un entorno virtual de Python.
3. Instala Pillow si planeas utilizar la interfaz gráfica con previsualización de texturas.

## Flujo de trabajo en línea de comandos
El script ofrece tres subcomandos principales que puedes ejecutar desde una terminal:

### 1. Extraer un archivo
```bash
python rs.py extract <ruta/al/archivo.asr> <directorio_salida>
```
- Copia todos los recursos descritos por la tabla RSFL al directorio indicado.
- Genera automáticamente un `manifest.json` que conserva offsets, tamaños y metadatos para facilitar el reempaquetado posterior.

### 2. Reempacar cambios
```bash
python rs.py repack <archivo_original.asr> <ruta/al/manifest.json> <directorio_modificado> <archivo_salida.asr>
```
- Reutiliza el `manifest.json` para reconstruir el contenedor respetando el orden y los offsets originales.
- Los recursos que cambiaron de tamaño se añaden al final del archivo y se actualizan sus punteros; las entradas controladas por RSCF mantienen su tamaño original para preservar la integridad del contenedor.

### 3. Crear un parche mínimo
```bash
python rs.py patch <archivo_original.asr> <ruta/al/manifest.json> <directorio_modificado> <archivo_parche.asr>
```
- Produce un archivo que solo contiene los recursos modificados, ideal para distribuir cambios pequeños sin compartir todo el paquete.

## Interfaz gráfica enfocada en texturas
Si tienes Tkinter disponible, puedes lanzar el visor y gestor de texturas con:
```bash
python rs.py gui
```
- Al iniciarse, pulsa **Open Archive** para seleccionar un archivo RS; el visor cargará únicamente las entradas identificadas como imágenes (DDS, PNG, JPG, BMP, GIF, TGA, TIFF, etc.).
- Puedes previsualizar la textura seleccionada (requiere Pillow) y revisar metadatos como el formato detectado y el tamaño original.
- Utiliza **Import Replacement** para seleccionar una nueva textura que sustituya la original. El reemplazo se queda en cola hasta que generes un parche o guardes un archivo actualizado.
- Con **Create Patch** generarás un archivo con solo los reemplazos en cola, mientras que **Save Archive As** crea una copia completa del archivo original con los cambios aplicados.

## Buenas prácticas
- Conserva siempre una copia de seguridad del archivo original antes de aplicar reemplazos.
- Trabaja en un directorio separado para los recursos extraídos y otro para los modificados; esto facilita comparar cambios y evita sobrescribir archivos.
- Documenta los reemplazos que realices. El programa puede generar un registro `.replacements.json` junto al parche para que puedas reimportar los cambios más adelante.

Con esta guía podrás realizar un ciclo completo de edición de texturas: extraer ➜ modificar ➜ probar en la GUI ➜ generar parche o reempaquetar. Recuerda que, por ahora, la herramienta está pensada para imágenes; otros tipos de recursos se mantienen sin modificaciones.
