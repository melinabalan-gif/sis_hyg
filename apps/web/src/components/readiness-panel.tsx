const statuses = [
  { label: "Interfaz", value: "disponible", tone: "ready" },
  {
    label: "Servicios operativos",
    value: "pendientes de configuración",
    tone: "pending",
  },
  { label: "Datos de operación", value: "no cargados", tone: "neutral" },
] as const;

export function ReadinessPanel() {
  return (
    <section className="readiness" aria-labelledby="readiness-title">
      <div>
        <p className="eyebrow">Estado del baseline</p>
        <h2 id="readiness-title">Una interfaz honesta desde el primer día</h2>
        <p className="readiness__intro">
          Esta versión confirma la base visual. No presenta indicadores ni
          conclusiones hasta que los servicios, permisos y fuentes estén
          verificados.
        </p>
      </div>
      <dl className="status-list">
        {statuses.map((status) => (
          <div className="status-row" key={status.label}>
            <dt>{status.label}</dt>
            <dd>
              <span className={`status-pill status-pill--${status.tone}`}>
                {status.value}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
