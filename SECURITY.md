# Security policy / Política de seguridad

## Reporting

Please report vulnerabilities privately through GitHub's private vulnerability reporting (the repository's Security tab,
"Report a vulnerability"), not in public issues. Reports are acknowledged within a week; a fix is released as a patch
version and credited in the changelog unless you ask otherwise.

Por favor, informa de vulnerabilidades en privado con el aviso privado de vulnerabilidades de GitHub (pestaña Security
del repositorio, "Report a vulnerability"), no en issues públicos. Se responde en una semana como mucho; el arreglo sale
como versión de parche y se te cita en el changelog salvo que pidas lo contrario.

## Supported versions

The latest release. exactfig has no dependencies, so there is nothing else to update.

## Scope

In scope: anything that lets `exactfig verify` accept a file that its recipe does not produce, a recipe that carries
image data past the parameter schemas, a manifest edit that goes undetected, a proof or certificate (`data.refutation`,
`data.circuit_refutation`, `data.pratt`) accepted for a claim it does not prove, or an RO-Crate (`exactfig crate`) that
describes files other than the recorded ones; crashes, hangs or resource exhaustion when reading untrusted recipes,
manifests or input files (CSV, NPY, PGM/PPM, PNG, JSON, catalogues, colourings, instance masks, triangles, b-files,
Pratt certificates, LRAT proofs, circuits).

`verify` reads files from the manifest folder only and never executes code from recipes, manifests or data: generators
are looked up in the built-in registry by name, and input files are parsed as data, never evaluated.
