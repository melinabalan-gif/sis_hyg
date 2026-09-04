import { EnvironmentBanner } from "../src/components/environment-banner";
import { ReadinessPanel } from "../src/components/readiness-panel";

const principles = [
  {
    index: "01",
    title: "Alcance controlado",
    text: "Cada vista combinará organización, rol, permiso y alcance de obra antes de mostrar información.",
    accent: "blue",
  },
  {
    index: "02",
    title: "Privacidad desde el diseño",
    text: "Los datos recuperables se cifran; los tokens de comparación no sustituyen el cifrado ni anonimizan personas.",
    accent: "green",
  },
  {
    index: "03",
    title: "Experiencia adaptable",
    text: "La misma base acompaña escritorio y campo, con estados explícitos y preparación para operación offline.",
    accent: "amber",
  },
] as const;

export default function HomePage() {
  return (
    <main>
      <EnvironmentBanner />

      <div className="shell">
        <header className="topbar">
          <a className="brand" href="#inicio" aria-label="H&S Gestión, inicio">
            <span className="brand__mark" aria-hidden="true">
              <span>H</span>
            </span>
            <span className="brand__copy">
              <strong>H&amp;S</strong>
              <small>GESTIÓN</small>
            </span>
          </a>
          <div className="topbar__meta">
            <span className="topbar__tag">Baseline V1</span>
            <span className="topbar__availability">
              <span aria-hidden="true" /> Interfaz disponible
            </span>
          </div>
        </header>

        <section className="hero" id="inicio" aria-labelledby="hero-title">
          <div className="hero__copy">
            <p className="eyebrow">Higiene y seguridad · Obras civiles</p>
            <h1 id="hero-title">Una base segura para gestionar H&amp;S</h1>
            <p className="hero__lead">
              El primer corte técnico prioriza aislamiento, trazabilidad y una
              experiencia clara antes de incorporar información operativa.
            </p>
            <div className="hero__actions" aria-label="Acciones informativas">
              <a className="button button--primary" href="#estado">
                Ver estado del baseline
              </a>
              <a className="button button--secondary" href="#principios">
                Conocer los principios
              </a>
            </div>
          </div>

          <aside
            className="hero__signal"
            aria-label="Circuito objetivo de la plataforma"
          >
            <p className="hero__signal-label">Circuito V1</p>
            <ol>
              <li>
                <span>Preparar</span>
                <strong>Obra y legajos</strong>
              </li>
              <li>
                <span>Verificar</span>
                <strong>Auditoría de campo</strong>
              </li>
              <li>
                <span>Resolver</span>
                <strong>Desvíos y evidencia</strong>
              </li>
              <li>
                <span>Trazar</span>
                <strong>Cierre e informe</strong>
              </li>
            </ol>
            <p className="hero__signal-note">
              Sin automatizar criterio profesional ni afirmar cumplimiento
              legal.
            </p>
          </aside>
        </section>

        <section
          className="principles"
          id="principios"
          aria-labelledby="principles-title"
        >
          <div className="section-heading">
            <p className="eyebrow">Decisiones fundacionales</p>
            <h2 id="principles-title">Construir confianza antes que volumen</h2>
          </div>
          <div className="principles__grid">
            {principles.map((principle) => (
              <article
                className={`principle principle--${principle.accent}`}
                key={principle.index}
              >
                <span className="principle__index">{principle.index}</span>
                <h3>{principle.title}</h3>
                <p>{principle.text}</p>
              </article>
            ))}
          </div>
        </section>

        <div id="estado">
          <ReadinessPanel />
        </div>

        <footer>
          <p>H&amp;S Gestión V1</p>
          <p>Entorno sintético · Buenos Aires (UTC−03:00)</p>
        </footer>
      </div>
    </main>
  );
}
