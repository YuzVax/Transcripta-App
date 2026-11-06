# Firma digital y aviso de Windows

## Estado de esta edición

`Transcripta_v2.exe` **no está firmado** con un certificado de firma de código.
No se utiliza un certificado autofirmado o de prueba para aparentar confianza.
Incluso una firma válida no garantiza que Windows deje de mostrar avisos.

## Descarga oficial y comprobación

Usa las [versiones de YuzVax/Transcripta-App](https://github.com/YuzVax/Transcripta-App/releases).
En **Assets**, descarga `Transcripta_v2.exe` y `Transcripta_v2.exe.sha256`.

La edición de distribución **v2.0.0** reutiliza, sin modificar, el ejecutable
validado con versión interna **1.1.10**. Su SHA256 es:

```text
88299080c1d25972081899e4e96365c82c9fec21617938ac39b65d993f028f0e
```

Para comprobarlo, abre **Símbolo del sistema** (cmd) en la carpeta de descarga:

```bat
certutil -hashfile Transcripta_v2.exe SHA256
```

Compara el valor completo con el publicado para esa misma versión. **Si difiere,
no abras el archivo.** SHA256 confirma que coincide con la descarga publicada;
no sustituye una firma digital ni garantiza que un programa sea inocuo.

## Si aparece «Windows protegió su PC»

Solo si has descargado el archivo del repositorio oficial y verificado su
integridad: **Más información → Ejecutar de todas formas**.

En **Propiedades → General** también puede aparecer **Desbloquear** para un
archivo descargado de Internet. Es opcional y solo procede con el archivo
oficial ya verificado.

No desactives SmartScreen ni el antivirus. Si una política de Windows o de tu
organización impide continuar, no intentes saltarte esa restricción.

## Si el antivirus detecta una amenaza

Una detección explícita de malware **no es lo mismo** que un editor desconocido.
No debe descartarse automáticamente como falso positivo. Conserva el nombre de
la detección, el hash y la procedencia del archivo y revisa el caso con el
proveedor del antivirus antes de ejecutarlo. No añadas exclusiones generales.

No se afirma que una alerta de PowerShell de otro proceso provenga de
Transcripta: identificar su origen requiere revisar el evento y el script
concretos. Los comandos de verificación anteriores no necesitan PowerShell.
