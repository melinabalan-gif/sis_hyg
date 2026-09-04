const PROTOTYPE_NOTICE =
  "PROTOTIPO · DATOS 100 % SINTÉTICOS · SIN VALIDEZ OPERATIVA";

export function EnvironmentBanner() {
  return (
    <div
      className="environment-banner"
      role="status"
      aria-label="Estado del entorno"
    >
      <span className="environment-banner__dot" aria-hidden="true" />
      <strong>{PROTOTYPE_NOTICE}</strong>
    </div>
  );
}

export { PROTOTYPE_NOTICE };
