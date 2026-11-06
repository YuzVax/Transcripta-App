# Guía de uso

[Volver al inicio](../README.md)

## Preparar la sesión

Abre `Transcripta_v2.exe` normalmente, sin administrador, y espera a la extracción.
El lanzador usa una carpeta temporal por sesión dentro de:

```text
%LocalAppData%\Transcripta\sesion-<id>\
```

Los modelos no están incluidos en el EXE: se descargan al necesitarlos. Tras
cerrar se eliminan junto con la sesión, por lo que necesitarás descargarlos
otra vez al abrir de nuevo. El código fuente sin empaquetar no utiliza
automáticamente este aislamiento.

## Añadir audio o vídeo

Pulsa **Añadir archivos** o arrastra archivos desde el Explorador. Se omiten
carpetas, formatos no admitidos y duplicados. Si el arrastre falla, usa el botón;
Windows puede bloquearlo entre programas con permisos distintos.

## Transcribir

1. Selecciona **small**, **medium** o **large-v3**. Empieza con small.
2. Selecciona el idioma de entrada o **Detectar automáticamente**.
3. Si conoces nombres o términos difíciles, añade vocabulario de apoyo.
4. Pulsa **Transcribir** y espera a que termine la cola.

El progreso pondera la cola por número de archivos, no por la duración de cada
uno. No es una predicción exacta del tiempo restante. Durante el trabajo se
bloquean los controles incompatibles para evitar cambios simultáneos.

**Cancelar** detiene la cola y conserva los resultados de los archivos ya
terminados. La conversión con FFmpeg se puede detener; la inferencia responde
entre segmentos. Una descarga o un cálculo nativo en curso puede tardar en
responder. Un archivo interrumpido no se marca como transcripción completa.

## Traducir

Elige un destino entre **español, inglés, italiano, portugués, francés, alemán
y ruso**. Argos Translate descargará los paquetes que falten. Según su catálogo,
la traducción puede ser directa o pasar por inglés. Si no existe una ruta
compatible, la aplicación lo indicará.

El texto se traduce en el equipo; descargar paquetes e índices sí requiere
Internet. Revisa el resultado, especialmente nombres, cifras y matices.

## Guardar

Usa **TXT** para texto o **SRT / VTT** para subtítulos. Elige una carpeta propia,
fuera de la sesión temporal. Los originales y estos archivos exportados no se
borran al cerrar. La última carpeta elegida se recuerda solo durante la sesión.

## Cerrar o abrir otra vez

Exporta primero lo que quieras conservar. Al cerrar, el lanzador detiene sus
subprocesos y reintenta la limpieza de la sesión. Tras un apagón o un cierre
forzado, intenta retirar las sesiones huérfanas en el siguiente inicio.

**Abrir una segunda vez cierra la instancia anterior**, por lo que puede perderse
el trabajo sin exportar. No lo uses para detener una tarea de forma habitual:
es preferible cancelar desde la interfaz.

Si un archivo queda bloqueado por Windows, la limpieza puede necesitar un
reintento. Esto no es borrado forense ni elimina registros del sistema,
memoria virtual, registros del antivirus o copias de seguridad.

## Problemas habituales

| Problema | Qué revisar |
|----------|-------------|
| Tarda en preparar la app | La extracción incluye Python, FFmpeg y bibliotecas; espera a que termine |
| No descarga un modelo | Conexión, espacio libre y acceso a los proveedores de modelos |
| Large-v3 tarda mucho | Esta edición usa CPU; prueba small y cierra otras tareas pesadas |
| No funciona arrastrar | Abre la app sin administrador o usa Añadir archivos |
| No hay traducción para un par | Depende de los paquetes disponibles en Argos, directos o vía inglés |
| Aviso de Windows | Revisa [AVISO_SMARTSCREEN.md](../AVISO_SMARTSCREEN.md); no desactives protecciones |
| Resultados incorrectos | Revisa idioma, calidad de grabación, vocabulario y modelo |
