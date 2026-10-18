# Security policy / Política de seguridad

This is a stub until the project is public. / Borrador hasta que el proyecto sea público.

## Reporting

Please report vulnerabilities privately through the repository's private vulnerability reporting (GitHub "Report a
vulnerability"), not in public issues. A contact address will be added before the first public release.

Por favor, informa de vulnerabilidades en privado con el aviso privado de vulnerabilidades del repositorio, no en issues
públicos.

## Scope

In scope: anything that lets `exactfig verify` accept a file that its recipe does not produce, a recipe that carries image
data past the parameter schemas, or a manifest edit that goes undetected; crashes or resource exhaustion when reading untrusted
PNG, MIDI, recipe or manifest files.

`verify` reads files from the manifest folder only and never executes code from recipes or manifests: generators are looked up
in the built-in registry by name.
