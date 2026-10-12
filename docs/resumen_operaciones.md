# Resumen para Operaciones: conciliación de facturas

## Qué hace la herramienta

Lee las facturas de los transportistas (PDF, escaneos y fotos), las compara con el registro de cargas y le dice cuáles debe revisar una persona y por qué. La tarifa del registro es la que manda. La herramienta no aprueba ni paga nada: solo avisa.

## Cómo abrir el reporte

1. Abra `reporte.html` con doble clic. Se abre en el navegador y no necesita internet. Si prefiere Excel, abra `reporte.csv`.
2. Empiece por "Excepciones por severidad": es la lista de lo que hay que revisar, con la razón y la acción sugerida.

## Cómo leer las etiquetas

- **ALTA:** revisar antes de pagar.
- **MEDIA:** algo raro, menos grave.
- **BAJA:** detalle menor.
- **NADA QUE REVISAR:** la herramienta no encontró nada. No significa "aprobada": si algo le parece raro, abra el PDF.

## Qué hacer con cada aviso

| Código | Qué significa | Qué hacer |
|---|---|---|
| NO_LOAD_MATCH | La carga de la factura no está en el registro. Las cargas "sugeridas" son solo una pista. | Buscar la carga correcta con el transportista. No pagar hasta confirmarla. |
| AMOUNT_MISMATCH | El monto es distinto al pactado. | No pagar la diferencia sin aprobación. Pedir aclaración al transportista. |
| ANNOTATED_AMOUNT | Hay un cobro extra escrito a mano. | Pedir sustento y autorizarlo por escrito antes de pagar. |
| DUPLICATE_INVOICE_NUMBER | Parece la misma factura recibida dos veces. | Conservar una sola copia y pagar una vez. |
| DUPLICATE_LOAD_INVOICE | Hay dos facturas distintas para la misma carga. | Confirmar cuál es la válida y rechazar la otra para no pagar dos veces. |
| CURRENCY_MISMATCH | La moneda de la factura no es la pactada. No se compara el monto. | Pedir al transportista que la corrija o confirmar el cambio. |
| CARRIER_MISMATCH | El transportista de la factura no es el de esa carga. | Confirmar que sea el transportista de la carga. |
| INVOICE_BEFORE_SHIPMENT | La factura tiene fecha anterior al embarque. | Revisar la fecha en el PDF. |
| MISSING_FIELD, EXTRACTION_MISMATCH, SINGLE_READ_LOW_LEGIBILITY, FILE_UNREADABLE | Falta un dato, un dato leído no coincide con el PDF, la imagen es difícil de leer o el archivo no abre. | Revisar la factura a mano en el PDF. Si hace falta, pedir una copia legible al transportista. |
| CURRENCY_NOT_PRINTED | La factura no dice la moneda. Se usó la del registro. | Confirmar la moneda si el monto es importante. |

Al final del reporte hay una lista de cargas del registro sin factura. Es solo informativa: puede que la factura aún no haya llegado.

## Cuándo pedir ayuda

- El reporte no abre, o aparece un "Aviso" en "Datos de la corrida".
- Aparece un código que no está en esta tabla.
- Una razón no cuadra con lo que ve en el PDF original.

La herramienta puede equivocarse al leer fotos o notas escritas a mano. Ante la duda, abra el PDF.