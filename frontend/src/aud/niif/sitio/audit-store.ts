// SUSTITUTO — NO es copia del sitio.
//
// En auditbrain-site, lib/audit-store.ts es código del servidor (D1, sesión
// de ChatGPT, cabeceras). engagement-context.ts solo le pide la clase
// HttpError; este archivo le da exactamente eso para que engagement-context.ts
// y reconstruction/protocol.ts se usen sin tocarlos. Por eso queda fuera de
// MANIFIESTO.json.
export class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}
