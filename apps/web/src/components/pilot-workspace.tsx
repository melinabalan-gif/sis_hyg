"use client";

import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  PILOT_ACTORS,
  actorRole,
  formatDate,
  formatDateTime,
  downloadWorksiteReport,
  getWorksite,
  listWorksites,
  type Audit,
  type DocumentSubjectKind,
  type Finding,
  type PilotActor,
  type WorksiteDetail,
  type WorksiteSummary,
  postPilot,
} from "../lib/pilot-api";

const STEPS = [
  ["overview", "Resumen"],
  ["stages", "Etapas"],
  ["contractors", "Contratistas"],
  ["people", "Personal"],
  ["documents", "Documentación"],
  ["machines", "Maquinarias"],
  ["audit", "Auditoría"],
  ["followup", "Seguimiento"],
] as const;

type Step = (typeof STEPS)[number][0];

function fieldValue(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function optionalField(form: FormData, name: string): string | undefined {
  const value = fieldValue(form, name);
  return value || undefined;
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value
    .toLowerCase()
    .replaceAll("_", "-")
    .replaceAll(" ", "-");
  return (
    <span className={`status-badge status-badge--${normalized}`}>{value}</span>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>;
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <article className={`card ${className}`.trim()}>{children}</article>;
}

const DOCUMENT_STATUS_LABELS = [
  ["FALTANTE", "Faltante"],
  ["PENDIENTE", "Pendiente"],
  ["RECHAZADO", "Rechazado"],
  ["POR_VENCER", "Por vencer"],
  ["VENCIDO", "Vencido"],
  ["VIGENTE", "Vigente"],
] as const;

const FINDING_STATUS_LABELS = [
  ["ABIERTO", "Abierto"],
  ["EN_CORRECCION", "En corrección"],
  ["PENDIENTE_VERIFICACION", "Pendiente de verificación"],
  ["CERRADO", "Cerrado"],
] as const;

const MACHINE_STATUS_LABELS = [
  ["OPERATIVA", "Operativa"],
  ["CON_OBSERVACIONES", "Con observaciones"],
  ["FUERA_DE_SERVICIO", "Fuera de servicio"],
] as const;

function DashboardPanel({
  eyebrow,
  title,
  target,
  onStep,
  children,
}: {
  eyebrow: string;
  title: string;
  target: Step;
  onStep: (step: Step) => void;
  children: ReactNode;
}) {
  return (
    <Card className="dashboard-panel">
      <div className="dashboard-panel__header">
        <div>
          <p className="kicker">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
        <button
          className="dashboard-panel__link"
          onClick={() => onStep(target)}
          type="button"
        >
          Ver detalle →
        </button>
      </div>
      {children}
    </Card>
  );
}

function DashboardStatusList({
  statuses,
  counts,
}: {
  statuses: readonly (readonly [string, string])[];
  counts: Record<string, number>;
}) {
  return (
    <ul className="dashboard-status-list">
      {statuses.map(([key, label]) => (
        <li key={key}>
          <span>{label}</span>
          <strong>{counts[key] ?? 0}</strong>
        </li>
      ))}
    </ul>
  );
}

export function PilotWorkspace() {
  const [actor, setActor] = useState<PilotActor>("tecnico");
  const [worksites, setWorksites] = useState<WorksiteSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorksiteDetail | null>(null);
  const [step, setStep] = useState<Step>("overview");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const role = actorRole(actor);
  const canManageResources = role === "TECNICO" || role === "RESPONSABLE_HYS";
  const canManageAudit = role === "AUDITOR" || role === "RESPONSABLE_HYS";
  const canVerify = role === "RESPONSABLE_HYS";

  const loadList = useCallback(async (nextActor: PilotActor) => {
    const items = await listWorksites(nextActor);
    setWorksites(items);
    return items;
  }, []);

  const loadDetail = useCallback(async (id: string, nextActor: PilotActor) => {
    const item = await getWorksite(id, nextActor);
    setDetail(item);
    return item;
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const items = await loadList(actor);
        if (!active) return;
        if (selectedId && items.some((item) => item.id === selectedId)) {
          await loadDetail(selectedId, actor);
        } else {
          setSelectedId(null);
          setDetail(null);
        }
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "No se pudo cargar el piloto.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [actor, loadDetail, loadList, selectedId]);

  const refresh = useCallback(async () => {
    await loadList(actor);
    if (selectedId) await loadDetail(selectedId, actor);
  }, [actor, loadDetail, loadList, selectedId]);

  async function selectWorksite(id: string) {
    setSelectedId(id);
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await loadDetail(id, actor);
      setStep("overview");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "No se pudo abrir la obra.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function mutate(
    key: string,
    path: string,
    payload: Record<string, unknown>,
    success: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await postPilot(path, actor, payload);
      await refresh();
      setNotice(success);
      return true;
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "La operación no pudo completarse.",
      );
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function createWorksite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setBusy("worksite");
    setError(null);
    setNotice(null);
    try {
      const created = await postPilot<WorksiteSummary>("/worksites", actor, {
        code: fieldValue(form, "code"),
        name: fieldValue(form, "name"),
        jurisdiction: fieldValue(form, "jurisdiction"),
      });
      await loadList(actor);
      setSelectedId(created.id);
      await loadDetail(created.id, actor);
      setStep("overview");
      target.reset();
      setNotice(
        "Obra creada y abierta. Ya podés completar su legajo operativo.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "No se pudo crear la obra.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function downloadReport() {
    setBusy("report");
    setError(null);
    setNotice(null);
    try {
      if (!detail) return;
      const blob = await downloadWorksiteReport(detail.id, actor);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${detail.code.toLowerCase()}-reporte.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("PDF generado desde el estado persistido de la obra.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo generar el PDF de la obra.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function submitForm(
    event: FormEvent<HTMLFormElement>,
    key: string,
    path: string,
    build: (form: FormData) => Record<string, unknown>,
    success: string,
  ) {
    event.preventDefault();
    const target = event.currentTarget;
    const ok = await mutate(key, path, build(new FormData(target)), success);
    if (ok) target.reset();
  }

  const activeAudit = useMemo(() => {
    if (!detail?.audits.length) return null;
    return (
      detail.audits.find((audit) => audit.status === "EN_CURSO") ??
      detail.audits.at(-1)!
    );
  }, [detail]);

  const totalRecords = detail
    ? detail.contractors.length +
      detail.stages.length +
      detail.people.length +
      detail.documents.length +
      detail.machines.length
    : 0;

  return (
    <div className="pilot-layout">
      <aside className="worksite-rail" aria-label="Selector de obras">
        <div className="rail-heading">
          <div>
            <p className="kicker">Piloto funcional</p>
            <h2>Obras</h2>
          </div>
          <span className="counter" aria-label={`${worksites.length} obras`}>
            {worksites.length}
          </span>
        </div>

        <div className="worksite-list">
          {loading && worksites.length === 0 ? (
            <p className="loading-copy">Cargando obras…</p>
          ) : null}
          {!loading && worksites.length === 0 ? (
            <EmptyState>
              Creá la primera obra sintética para iniciar el recorrido.
            </EmptyState>
          ) : null}
          {worksites.map((worksite) => (
            <button
              className={`worksite-button ${selectedId === worksite.id ? "is-active" : ""}`}
              key={worksite.id}
              onClick={() => void selectWorksite(worksite.id)}
              type="button"
            >
              <span>{worksite.code}</span>
              <strong>{worksite.name}</strong>
              <small>{worksite.status}</small>
            </button>
          ))}
        </div>

        <details className="create-panel" open={worksites.length === 0}>
          <summary>Nueva obra</summary>
          <form onSubmit={(event) => void createWorksite(event)}>
            <Field label="Código">
              <input
                name="code"
                placeholder="OBR-001"
                required
                maxLength={64}
              />
            </Field>
            <Field label="Nombre">
              <input
                name="name"
                placeholder="Ampliación planta piloto"
                required
                maxLength={200}
              />
            </Field>
            <Field label="Jurisdicción">
              <input
                name="jurisdiction"
                placeholder="Provincia / municipio"
                required
                maxLength={200}
              />
            </Field>
            <button
              className="button button--primary"
              disabled={busy !== null || !canManageResources}
            >
              {busy === "worksite" ? "Creando…" : "Crear y abrir"}
            </button>
            {!canManageResources ? (
              <small className="permission-note">
                Usá Técnico o Responsable H&amp;S para crear obras.
              </small>
            ) : null}
          </form>
        </details>
      </aside>

      <section className="workspace" aria-label="Espacio de trabajo de la obra">
        <header className="workspace-header">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">
              H
            </span>
            <div>
              <strong>H&amp;S Gestión</strong>
              <span>Flujo vertical del piloto</span>
            </div>
          </div>
          <label className="actor-switcher">
            <span>Actuar como</span>
            <select
              value={actor}
              onChange={(event) => {
                setLoading(true);
                setError(null);
                setNotice(null);
                setActor(event.target.value as PilotActor);
              }}
            >
              {PILOT_ACTORS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="pilot-notice">
          <span aria-hidden="true">●</span>
          Identidades y registros exclusivamente sintéticos. El selector
          representa roles del piloto, no una sesión productiva.
        </div>

        <div className="message-stack" aria-live="polite" aria-atomic="true">
          {error ? <p className="message message--error">{error}</p> : null}
          {notice ? <p className="message message--success">{notice}</p> : null}
        </div>

        {!selectedId || !detail ? (
          <section className="welcome-panel">
            <span className="welcome-panel__number">01</span>
            <p className="kicker">Punto de partida</p>
            <h1>Creá o abrí una obra</h1>
            <p>
              Desde acá vas a recorrer contratistas, personal, vencimientos,
              maquinarias, auditoría y cierre independiente del desvío con datos
              persistentes.
            </p>
            <ol className="flow-preview">
              <li>Preparar el legajo</li>
              <li>Ejecutar el control</li>
              <li>Corregir y verificar</li>
            </ol>
          </section>
        ) : (
          <>
            <div className="worksite-titlebar">
              <div>
                <p className="kicker">{detail.code}</p>
                <h1>{detail.name}</h1>
              </div>
              <div className="titlebar-meta">
                <span>Jurisdicción: {detail.jurisdiction}</span>
                <StatusBadge value={detail.status} />
                <span>{totalRecords} registros de legajo</span>
              </div>
            </div>

            <nav
              className="step-tabs"
              aria-label="Etapas del flujo"
              role="tablist"
            >
              {STEPS.map(([value, label], index) => (
                <button
                  aria-selected={step === value}
                  className={step === value ? "is-active" : ""}
                  key={value}
                  onClick={() => setStep(value)}
                  role="tab"
                  type="button"
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  {label}
                </button>
              ))}
            </nav>

            <div className="step-content" role="tabpanel">
              {step === "overview" ? (
                <Overview
                  detail={detail}
                  onDownloadReport={() => void downloadReport()}
                  onStep={setStep}
                />
              ) : null}
              {step === "stages" ? (
                <StagesStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageResources}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "stage",
                      `/worksites/${detail.id}/stages`,
                      (form) => ({
                        code: fieldValue(form, "code"),
                        name: fieldValue(form, "name"),
                        started_on: fieldValue(form, "started_on"),
                        ended_on: optionalField(form, "ended_on"),
                        sector: optionalField(form, "sector"),
                        notes: optionalField(form, "notes"),
                      }),
                      "Etapa registrada en la línea temporal de la obra.",
                    )
                  }
                />
              ) : null}
              {step === "contractors" ? (
                <ContractorsStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageResources}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "contractor",
                      `/worksites/${detail.id}/contractors`,
                      (form) => ({
                        legal_name: fieldValue(form, "legal_name"),
                        trade: fieldValue(form, "trade"),
                        started_on: optionalField(form, "started_on"),
                      }),
                      "Contratista asignado a la obra.",
                    )
                  }
                />
              ) : null}
              {step === "people" ? (
                <PeopleStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageResources}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "person",
                      `/worksites/${detail.id}/people`,
                      (form) => ({
                        display_name: fieldValue(form, "display_name"),
                        role_label: fieldValue(form, "role_label"),
                        contractor_id: fieldValue(form, "contractor_id"),
                        started_on: optionalField(form, "started_on"),
                      }),
                      "Persona sintética asignada al contratista.",
                    )
                  }
                />
              ) : null}
              {step === "documents" ? (
                <DocumentsStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageResources}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "document",
                      `/worksites/${detail.id}/documents`,
                      (form) => {
                        const [subjectKind, subjectId] = fieldValue(
                          form,
                          "subject",
                        ).split(":") as [DocumentSubjectKind, string];
                        return {
                          title: fieldValue(form, "title"),
                          document_type: fieldValue(form, "document_type"),
                          review_status: fieldValue(form, "review_status"),
                          valid_from: optionalField(form, "valid_from"),
                          expires_on: optionalField(form, "expires_on"),
                          notes: optionalField(form, "notes"),
                          subject_kind: subjectKind,
                          subject_id: subjectId,
                        };
                      },
                      "Documento registrado; su vigencia se recalculó.",
                    )
                  }
                  onVersionSubmit={(event, documentId) =>
                    void submitForm(
                      event,
                      `document-version-${documentId}`,
                      `/worksites/${detail.id}/documents/${documentId}/versions`,
                      (form) => ({
                        title: fieldValue(form, "version_title"),
                        document_type: fieldValue(
                          form,
                          "version_document_type",
                        ),
                        review_status: fieldValue(
                          form,
                          "version_review_status",
                        ),
                        valid_from: optionalField(form, "version_valid_from"),
                        expires_on: optionalField(form, "version_expires_on"),
                        notes: optionalField(form, "version_notes"),
                      }),
                      "Nueva versión registrada; la vista actual fue actualizada.",
                    )
                  }
                />
              ) : null}
              {step === "machines" ? (
                <MachinesStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageResources}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "machine",
                      `/worksites/${detail.id}/machines`,
                      (form) => ({
                        internal_code: fieldValue(form, "internal_code"),
                        description: fieldValue(form, "description"),
                        status: fieldValue(form, "status"),
                        reason: fieldValue(form, "reason"),
                        contractor_id: optionalField(form, "contractor_id"),
                      }),
                      "Maquinaria asignada con inspección inicial trazada.",
                    )
                  }
                  onInspection={(event, machineId) =>
                    void submitForm(
                      event,
                      `machine-inspection-${machineId}`,
                      `/worksites/${detail.id}/machines/${machineId}/inspections`,
                      (form) => ({
                        resulting_status: fieldValue(form, "resulting_status"),
                        reason: fieldValue(form, "inspection_reason"),
                      }),
                      "Reinspección registrada; estado y versión actualizados.",
                    )
                  }
                />
              ) : null}
              {step === "audit" ? (
                <AuditStep
                  detail={detail}
                  audit={activeAudit}
                  busy={busy}
                  canManage={canManageAudit}
                  onStart={() =>
                    void mutate(
                      "audit-start",
                      `/worksites/${detail.id}/audits`,
                      {},
                      "Auditoría iniciada. Ya podés registrar el control.",
                    )
                  }
                  onControl={(event, catalogCode) => {
                    if (!activeAudit) return;
                    void submitForm(
                      event,
                      "audit-control",
                      `/audits/${activeAudit.id}/controls`,
                      (form) => ({
                        catalog_code: catalogCode,
                        result: fieldValue(form, "result"),
                        reason: optionalField(form, "reason"),
                        severity_code: optionalField(form, "severity_code"),
                        finding_description: optionalField(
                          form,
                          "finding_description",
                        ),
                      }),
                      "Control registrado y desvío enlazado cuando corresponde.",
                    );
                  }}
                  onFinalize={() => {
                    if (!activeAudit) return;
                    void mutate(
                      "audit-finalize",
                      `/audits/${activeAudit.id}/finalize`,
                      {},
                      "Auditoría finalizada. Los controles quedaron congelados.",
                    );
                  }}
                />
              ) : null}
              {step === "followup" ? (
                <FollowupStep
                  detail={detail}
                  actor={actor}
                  busy={busy}
                  canVerify={canVerify}
                  onCorrection={(event, finding) =>
                    void submitForm(
                      event,
                      `correction-${finding.id}`,
                      `/findings/${finding.id}/corrections`,
                      (form) => ({
                        description: fieldValue(form, "description"),
                        evidence_note: fieldValue(form, "evidence_note"),
                      }),
                      "Corrección agregada al seguimiento.",
                    )
                  }
                  onSubmitVerification={(finding) =>
                    void mutate(
                      `submit-${finding.id}`,
                      `/findings/${finding.id}/submit-verification`,
                      {},
                      "Desvío enviado a verificación independiente.",
                    )
                  }
                  onVerify={(event, finding) =>
                    void submitForm(
                      event,
                      `verify-${finding.id}`,
                      `/findings/${finding.id}/verifications`,
                      (form) => ({
                        decision: fieldValue(form, "decision"),
                        notes: fieldValue(form, "notes"),
                      }),
                      "Verificación registrada y estado actualizado.",
                    )
                  }
                />
              ) : null}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Overview({
  detail,
  onStep,
  onDownloadReport,
}: {
  detail: WorksiteDetail;
  onStep: (step: Step) => void;
  onDownloadReport: () => void;
}) {
  const quickMetrics = [
    ["contractors", "Contratistas", detail.contractors.length],
    ["stages", "Etapas temporales", detail.stages.length],
    ["people", "Personal", detail.people.length],
    ["documents", "Documentos", detail.metrics.documents.total],
    ["machines", "Maquinarias", detail.metrics.machines.total],
    ["audit", "Auditorías", detail.audits.length],
    ["followup", "Desvíos", detail.metrics.findings.total],
  ] as const;
  const controls = detail.metrics.controls;
  const latestAudit = detail.metrics.latest_audit;
  const ratioLabel =
    controls.ratio === null
      ? "Sin base"
      : `${Math.round(controls.ratio * 100)}%`;
  return (
    <section>
      <div className="section-heading">
        <div>
          <p className="kicker">Estado de la obra</p>
          <h2>Recorrido operativo</h2>
        </div>
        <p>
          Un corte sintético de los registros visibles. Cada panel abre el
          detalle que lo respalda.
        </p>
      </div>
      <div className="metric-grid">
        {quickMetrics.map(([target, label, value], index) => (
          <button key={target} onClick={() => onStep(target)} type="button">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{value}</strong>
            <small>{label}</small>
          </button>
        ))}
      </div>
      <div className="dashboard-grid">
        <DashboardPanel
          eyebrow="01 · Legajo"
          onStep={onStep}
          target="documents"
          title="Documentación"
        >
          <p className="dashboard-total">
            <strong>{detail.metrics.documents.total}</strong> documentos
            visibles
          </p>
          <DashboardStatusList
            counts={detail.metrics.documents.by_status}
            statuses={DOCUMENT_STATUS_LABELS}
          />
          {!detail.metrics.documents.total ? (
            <EmptyState>No hay documentos registrados en esta obra.</EmptyState>
          ) : null}
        </DashboardPanel>

        <DashboardPanel
          eyebrow="02 · Seguimiento"
          onStep={onStep}
          target="followup"
          title="Desvíos"
        >
          <p className="dashboard-total">
            <strong>{detail.metrics.findings.total}</strong> desvíos visibles
          </p>
          <DashboardStatusList
            counts={detail.metrics.findings.by_status}
            statuses={FINDING_STATUS_LABELS}
          />
          <p className="dashboard-callout">
            Vencidos sin cerrar:{" "}
            <strong>{detail.metrics.findings.overdue}</strong>
          </p>
          {!detail.metrics.findings.total ? (
            <EmptyState>No hay desvíos registrados en esta obra.</EmptyState>
          ) : null}
        </DashboardPanel>

        <DashboardPanel
          eyebrow="03 · Activos"
          onStep={onStep}
          target="machines"
          title="Maquinarias"
        >
          <p className="dashboard-total">
            <strong>{detail.metrics.machines.total}</strong> maquinarias
            visibles
          </p>
          <DashboardStatusList
            counts={detail.metrics.machines.by_status}
            statuses={MACHINE_STATUS_LABELS}
          />
          {!detail.metrics.machines.total ? (
            <EmptyState>No hay maquinarias asignadas a esta obra.</EmptyState>
          ) : null}
        </DashboardPanel>

        <DashboardPanel
          eyebrow="04 · Auditoría"
          onStep={onStep}
          target="audit"
          title="Última auditoría y controles"
        >
          {latestAudit ? (
            <div className="dashboard-audit">
              <strong>{latestAudit.status}</strong>
              <span>Iniciada {formatDateTime(latestAudit.started_at)}</span>
              {latestAudit.finalized_at ? (
                <span>
                  Finalizada {formatDateTime(latestAudit.finalized_at)}
                </span>
              ) : null}
            </div>
          ) : (
            <EmptyState>No hay auditorías registradas en esta obra.</EmptyState>
          )}
          <div className="control-ratio">
            <div>
              <span>Ratio CUMPLE / evaluados</span>
              <strong>{ratioLabel}</strong>
            </div>
            <p>
              {controls.numerator} CUMPLE / {controls.denominator} evaluados
            </p>
          </div>
          <p className="dashboard-legend">
            Excluye NO_APLICA ({controls.excluded.no_aplica}) y NO_VERIFICADO (
            {controls.excluded.no_verificado}). Sólo usa controles registrados
            de la última auditoría visible.
          </p>
        </DashboardPanel>
      </div>
      <p className="dashboard-footnote">
        Corte sintético calculado {formatDateTime(detail.metrics.calculated_at)}{" "}
        · los contadores reconcilian con las pestañas de detalle.
      </p>
      <Card className="scope-card">
        <div>
          <StatusBadge value="ALCANCE PILOTO" />
          <h3>Cierre operativo verificable</h3>
          <p>
            Este corte llega hasta auditoría <strong>FINALIZADA</strong> y
            desvío <strong>CERRADO</strong> por un Responsable H&amp;S
            independiente.
          </p>
        </div>
        <p className="scope-card__aside">
          <button
            className="button button--dark"
            onClick={onDownloadReport}
            type="button"
          >
            Descargar PDF
          </button>
          Informe sintético generado sin archivos binarios ni datos reales.
        </p>
      </Card>
    </section>
  );
}

function StagesStep({ detail, busy, canManage, onSubmit }: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="02 · Tiempo operativo"
        title="Etapas"
        text="Registrá períodos de trabajo por obra. Las etapas pueden superponerse
          cuando distintos sectores avanzan en paralelo."
      />
      <div className="two-column">
        <Card>
          <h3>Agregar etapa</h3>
          <form
            className="form-grid"
            key={detail.stages.length}
            onSubmit={onSubmit}
          >
            <Field label="Código">
              <input
                name="code"
                required
                maxLength={64}
                placeholder="STG-001"
              />
            </Field>
            <Field label="Nombre">
              <input
                name="name"
                required
                maxLength={200}
                placeholder="Preparación"
              />
            </Field>
            <Field label="Inicio">
              <input name="started_on" required type="date" />
            </Field>
            <Field label="Fin (opcional)">
              <input name="ended_on" type="date" />
            </Field>
            <Field label="Sector (opcional)">
              <input name="sector" maxLength={120} placeholder="Norte" />
            </Field>
            <Field label="Notas (opcional)">
              <textarea
                name="notes"
                placeholder="Referencia operativa sintética"
              />
            </Field>
            <button
              className="button button--primary form-action"
              disabled={busy !== null || !canManage}
            >
              Guardar etapa
            </button>
          </form>
          {!canManage ? (
            <PermissionCopy text="Cambiá a Técnico o Responsable H&S para registrar etapas." />
          ) : null}
        </Card>
        <Card>
          <ListHeading count={detail.stages.length}>Línea temporal</ListHeading>
          {detail.stages.length ? (
            <ol className="stage-timeline">
              {detail.stages.map((stage) => (
                <li key={stage.id}>
                  <div className="stage-timeline__marker" aria-hidden="true" />
                  <div className="stage-timeline__content">
                    <div className="card-topline">
                      <span>{stage.code}</span>
                      <small>
                        {formatDate(stage.started_on)} —{" "}
                        {formatDate(stage.ended_on)}
                      </small>
                    </div>
                    <strong>{stage.name}</strong>
                    {stage.sector ? <span>Sector: {stage.sector}</span> : null}
                    {stage.notes ? <p>{stage.notes}</p> : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState>
              Todavía no hay etapas. Podés registrar períodos simultáneos para
              sectores distintos.
            </EmptyState>
          )}
        </Card>
      </div>
    </section>
  );
}

interface StepProps {
  detail: WorksiteDetail;
  busy: string | null;
  canManage: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onInspection?: (event: FormEvent<HTMLFormElement>, machineId: string) => void;
  onVersionSubmit?: (
    event: FormEvent<HTMLFormElement>,
    documentId: string,
  ) => void;
}

function ContractorsStep({ detail, busy, canManage, onSubmit }: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="03 · Legajo"
        title="Contratistas"
        text="Creá el maestro y su asignación a esta obra en una sola operación."
      />
      <div className="two-column">
        <Card>
          <h3>Asignar contratista</h3>
          <form className="form-grid" onSubmit={onSubmit}>
            <Field label="Razón social sintética">
              <input
                name="legal_name"
                required
                placeholder="Contratista Demo Norte"
              />
            </Field>
            <Field label="Rubro">
              <input name="trade" required placeholder="Montaje / excavación" />
            </Field>
            <Field label="Inicio">
              <input name="started_on" type="date" />
            </Field>
            <button
              className="button button--primary form-action"
              disabled={busy !== null || !canManage}
            >
              Guardar contratista
            </button>
          </form>
          {!canManage ? <PermissionCopy /> : null}
        </Card>
        <Card>
          <ListHeading count={detail.contractors.length}>Asignados</ListHeading>
          {detail.contractors.length ? (
            <ul className="record-list">
              {detail.contractors.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.legal_name}</strong>
                    <span>{item.trade}</span>
                  </div>
                  <small>
                    {item.started_on
                      ? `Desde ${formatDate(item.started_on)}`
                      : "Asignación activa"}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Todavía no hay contratistas en la obra.</EmptyState>
          )}
        </Card>
      </div>
    </section>
  );
}

function PeopleStep({ detail, busy, canManage, onSubmit }: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="04 · Dotación"
        title="Personal"
        text="Sólo referencias sintéticas: este piloto no acepta DNI, CUIL, teléfono ni correo."
      />
      <div className="two-column">
        <Card>
          <h3>Asignar persona</h3>
          <form className="form-grid" onSubmit={onSubmit}>
            <Field label="Nombre sintético">
              <input
                name="display_name"
                required
                placeholder="Operario Demo 01"
              />
            </Field>
            <Field label="Función">
              <input name="role_label" required placeholder="Operador" />
            </Field>
            <Field label="Contratista">
              <select name="contractor_id" required defaultValue="">
                <option value="" disabled>
                  Seleccionar…
                </option>
                {detail.contractors.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.legal_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Inicio">
              <input name="started_on" type="date" />
            </Field>
            <button
              className="button button--primary form-action"
              disabled={
                busy !== null || !canManage || detail.contractors.length === 0
              }
            >
              Guardar persona
            </button>
          </form>
          {!detail.contractors.length ? (
            <p className="permission-note">Primero asigná un contratista.</p>
          ) : null}
          {!canManage ? <PermissionCopy /> : null}
        </Card>
        <Card>
          <ListHeading count={detail.people.length}>
            Dotación registrada
          </ListHeading>
          {detail.people.length ? (
            <ul className="record-list">
              {detail.people.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.display_name}</strong>
                    <span>{item.role_label}</span>
                  </div>
                  <small>
                    {item.contractor_name ??
                      detail.contractors.find(
                        (contractor) => contractor.id === item.contractor_id,
                      )?.legal_name ??
                      "Contratista asignado"}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>No hay personal registrado.</EmptyState>
          )}
        </Card>
      </div>
    </section>
  );
}

function DocumentsStep({
  detail,
  busy,
  canManage,
  onSubmit,
  onVersionSubmit,
}: StepProps) {
  const subjects = [
    { value: `WORKSITE:${detail.id}`, label: `Obra · ${detail.name}` },
    ...detail.contractors.map((item) => ({
      value: `CONTRACTOR:${item.id}`,
      label: `Contratista · ${item.legal_name}`,
    })),
    ...detail.people.map((item) => ({
      value: `PERSON:${item.id}`,
      label: `Persona · ${item.display_name}`,
    })),
    ...detail.machines.map((item) => ({
      value: `MACHINE:${item.id}`,
      label: `Máquina · ${item.internal_code}`,
    })),
  ];
  return (
    <section>
      <StepHeading
        eyebrow="05 · Vigencias"
        title="Documentación"
        text="Se guardan metadatos y el sujeto explícito. La vigencia se deriva cada vez que abrís la obra."
      />
      <Card>
        <h3>Registrar documento</h3>
        <form className="form-grid form-grid--wide" onSubmit={onSubmit}>
          <Field label="Título">
            <input
              name="title"
              required
              placeholder="Seguro técnico sintético"
            />
          </Field>
          <Field label="Tipo">
            <input name="document_type" required placeholder="SEGURO" />
          </Field>
          <Field label="Sujeto">
            <select name="subject" required>
              {subjects.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Revisión">
            <select name="review_status" defaultValue="APROBADO">
              <option>APROBADO</option>
              <option>PENDIENTE</option>
              <option>RECHAZADO</option>
            </select>
          </Field>
          <Field label="Vigente desde">
            <input name="valid_from" type="date" />
          </Field>
          <Field label="Vence el">
            <input name="expires_on" type="date" />
          </Field>
          <Field label="Nota sintética">
            <input name="notes" placeholder="Referencia interna, sin archivo" />
          </Field>
          <button
            className="button button--primary"
            disabled={busy !== null || !canManage}
          >
            Guardar documento
          </button>
        </form>
        {!canManage ? <PermissionCopy /> : null}
      </Card>
      <div className="card-grid">
        {detail.documents.map((item) => (
          <Card key={item.id}>
            <div className="card-topline">
              <span>
                {item.document_type} · Versión {item.version}
              </span>
              <StatusBadge value={item.status} />
            </div>
            <h3>{item.title}</h3>
            <p className="muted">{item.subject_name ?? item.subject_kind}</p>
            <dl className="compact-details">
              <div>
                <dt>Revisión</dt>
                <dd>{item.review_status}</dd>
              </div>
              <div>
                <dt>Vencimiento</dt>
                <dd>{formatDate(item.expires_on)}</dd>
              </div>
            </dl>
            <details className="document-history">
              <summary>Historial ({item.versions.length} versiones)</summary>
              {item.versions.length ? (
                <ol className="document-history__list">
                  {item.versions.map((version) => (
                    <li key={version.id}>
                      <div>
                        <strong>
                          Versión {version.version_number} · {version.title}
                        </strong>
                        <span>
                          {version.document_type} · {version.review_status}
                        </span>
                      </div>
                      <small>
                        {formatDate(version.valid_from)} →{" "}
                        {formatDate(version.expires_on)} ·{" "}
                        {formatDateTime(version.created_at)}
                        {" · Actor "}
                        {version.actor_id.slice(0, 8)}
                      </small>
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState>No hay historial disponible.</EmptyState>
              )}
            </details>
            {onVersionSubmit ? (
              <details className="document-version-form">
                <summary>Registrar nueva versión</summary>
                <form
                  className="form-grid form-grid--wide"
                  onSubmit={(event) => onVersionSubmit(event, item.id)}
                >
                  <Field label="Título de la versión">
                    <input
                      name="version_title"
                      required
                      placeholder="Seguro técnico actualizado"
                    />
                  </Field>
                  <Field label="Tipo de la versión">
                    <input
                      name="version_document_type"
                      required
                      placeholder="SEGURO"
                    />
                  </Field>
                  <Field label="Revisión">
                    <select
                      name="version_review_status"
                      defaultValue="APROBADO"
                    >
                      <option>APROBADO</option>
                      <option>PENDIENTE</option>
                      <option>RECHAZADO</option>
                    </select>
                  </Field>
                  <Field label="Vigente desde">
                    <input name="version_valid_from" type="date" />
                  </Field>
                  <Field label="Vence el">
                    <input name="version_expires_on" type="date" />
                  </Field>
                  <Field label="Nota sintética">
                    <input
                      name="version_notes"
                      placeholder="Referencia interna, sin archivo"
                    />
                  </Field>
                  <button
                    className="button button--dark form-action"
                    disabled={
                      busy !== null ||
                      !canManage ||
                      busy === `document-version-${item.id}`
                    }
                  >
                    {busy === `document-version-${item.id}`
                      ? "Registrando…"
                      : "Registrar versión"}
                  </button>
                </form>
                {!canManage ? <PermissionCopy /> : null}
              </details>
            ) : null}
          </Card>
        ))}
      </div>
      {!detail.documents.length ? (
        <EmptyState>
          No hay documentos. Probá una fecha pasada y otra dentro de 30 días
          para validar los estados.
        </EmptyState>
      ) : null}
    </section>
  );
}

function MachinesStep({
  detail,
  busy,
  canManage,
  onSubmit,
  onInspection,
}: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="06 · Activos"
        title="Maquinarias"
        text="El estado inicial y cada transición nacen de una inspección con motivo y actor, no de un valor aislado."
      />
      <div className="two-column">
        <Card>
          <h3>Asignar maquinaria</h3>
          <form className="form-grid" onSubmit={onSubmit}>
            <Field label="Código interno">
              <input name="internal_code" required placeholder="MAQ-001" />
            </Field>
            <Field label="Descripción">
              <input
                name="description"
                required
                placeholder="Autoelevador sintético"
              />
            </Field>
            <Field label="Estado inicial">
              <select name="status" defaultValue="OPERATIVA">
                <option>OPERATIVA</option>
                <option>CON_OBSERVACIONES</option>
                <option>FUERA_DE_SERVICIO</option>
              </select>
            </Field>
            <Field label="Motivo de inspección">
              <textarea
                name="reason"
                required
                placeholder="Inspección inicial sin observaciones"
              />
            </Field>
            <Field label="Contratista (opcional)">
              <select name="contractor_id" defaultValue="">
                <option value="">Propia de la obra</option>
                {detail.contractors.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.legal_name}
                  </option>
                ))}
              </select>
            </Field>
            <button
              className="button button--primary form-action"
              disabled={busy !== null || !canManage}
            >
              Guardar maquinaria
            </button>
          </form>
          {!canManage ? <PermissionCopy /> : null}
        </Card>
        <Card>
          <ListHeading count={detail.machines.length}>
            Activos en obra
          </ListHeading>
          {detail.machines.length ? (
            <ul className="record-list">
              {detail.machines.map((item) => (
                <li className="machine-record" key={item.id}>
                  <div className="machine-record__heading">
                    <div>
                      <strong>
                        {item.internal_code} · {item.description}
                      </strong>
                      <span>
                        Versión {item.version} · Última inspección registrada
                      </span>
                    </div>
                    <StatusBadge value={item.status} />
                  </div>
                  {item.status === "FUERA_DE_SERVICIO" ? (
                    <p className="machine-warning">
                      FUERA_DE_SERVICIO: no debe operar hasta una inspección que
                      documente el levantamiento de la condición.
                    </p>
                  ) : null}
                  <details className="machine-history">
                    <summary>
                      Historial de inspecciones ({item.inspections?.length ?? 0}
                      )
                    </summary>
                    {item.inspections?.length ? (
                      <ol className="machine-history__list">
                        {item.inspections.map((inspection) => (
                          <li key={inspection.id}>
                            <div>
                              <strong>
                                <StatusBadge
                                  value={inspection.resulting_status}
                                />
                              </strong>
                              <span>{inspection.reason}</span>
                            </div>
                            <small>
                              {formatDateTime(inspection.inspected_at)} · Actor{" "}
                              {inspection.actor_id.slice(0, 8)}
                            </small>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <EmptyState>No hay historial disponible.</EmptyState>
                    )}
                  </details>
                  {onInspection ? (
                    <details className="machine-inspection-form">
                      <summary>Registrar reinspección o transición</summary>
                      <form
                        className="form-grid"
                        onSubmit={(event) => onInspection(event, item.id)}
                      >
                        <Field
                          label="Nuevo estado"
                          hint="El cambio queda registrado junto con el motivo y el actor sintético."
                        >
                          <select
                            defaultValue={item.status}
                            name="resulting_status"
                          >
                            <option>OPERATIVA</option>
                            <option>CON_OBSERVACIONES</option>
                            <option>FUERA_DE_SERVICIO</option>
                          </select>
                        </Field>
                        <Field label="Motivo de reinspección">
                          <textarea
                            name="inspection_reason"
                            placeholder="Describí el resultado y la causa de la transición"
                            required
                          />
                        </Field>
                        <button
                          className="button button--dark form-action"
                          disabled={
                            busy !== null ||
                            !canManage ||
                            busy === `machine-inspection-${item.id}`
                          }
                        >
                          {busy === `machine-inspection-${item.id}`
                            ? "Registrando…"
                            : "Registrar inspección"}
                        </button>
                      </form>
                      {!canManage ? (
                        <PermissionCopy text="Cambiá a Técnico o Responsable H&S para registrar reinspecciones." />
                      ) : null}
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>No hay maquinarias asignadas.</EmptyState>
          )}
        </Card>
      </div>
    </section>
  );
}

function AuditStep({
  detail,
  audit,
  busy,
  canManage,
  onStart,
  onControl,
  onFinalize,
}: {
  detail: WorksiteDetail;
  audit: Audit | null;
  busy: string | null;
  canManage: boolean;
  onStart: () => void;
  onControl: (event: FormEvent<HTMLFormElement>, catalogCode: string) => void;
  onFinalize: () => void;
}) {
  const inProgress = audit?.status === "EN_CURSO";
  const availableControls = audit?.available_controls ?? [];
  const answeredByCode = new Map(
    audit?.controls.map((control) => [control.catalog_code, control]) ?? [],
  );
  const answeredCount = availableControls.filter((control) =>
    answeredByCode.has(control.catalog_code),
  ).length;
  const progressLabel = `${answeredCount} de ${availableControls.length} controles respondidos`;
  return (
    <section>
      <StepHeading
        eyebrow="07 · Campo"
        title="Auditoría"
        text="El checklist es sintético y online. NO_CUMPLE crea el desvío de forma atómica."
      />
      {!audit || audit.status === "FINALIZADA" ? (
        <Card className="action-card">
          <div>
            <h3>Iniciar una auditoría</h3>
            <p>Fija obra, autor, editor y catálogo sintético publicado.</p>
          </div>
          <button
            className="button button--primary"
            disabled={busy !== null || !canManage}
            onClick={onStart}
            type="button"
          >
            Iniciar auditoría
          </button>
        </Card>
      ) : null}
      {!canManage ? (
        <PermissionCopy text="Cambiá a Auditor o Responsable H&S para operar la auditoría." />
      ) : null}
      {audit ? (
        <Card>
          <div className="audit-heading">
            <div>
              <p className="kicker">Auditoría {audit.id.slice(0, 8)}</p>
              <h3>Iniciada {formatDateTime(audit.started_at)}</h3>
            </div>
            <StatusBadge value={audit.status} />
          </div>
          <div
            aria-label={progressLabel}
            aria-valuemax={availableControls.length}
            aria-valuemin={0}
            aria-valuenow={answeredCount}
            className="audit-progress"
            role="progressbar"
          >
            <div>
              <span>Progreso del checklist</span>
              <strong>{progressLabel}</strong>
            </div>
            <div className="audit-progress__track" aria-hidden="true">
              <span
                style={{
                  width: availableControls.length
                    ? `${(answeredCount / availableControls.length) * 100}%`
                    : "0%",
                }}
              />
            </div>
          </div>
          <div className="control-list">
            {availableControls.map((catalogControl) => {
              const response = answeredByCode.get(catalogControl.catalog_code);
              return (
                <div className="control-item" key={catalogControl.catalog_code}>
                  <div className="control-row">
                    <div>
                      <span>{catalogControl.catalog_code}</span>
                      <strong>{catalogControl.catalog_title}</strong>
                    </div>
                    <StatusBadge value={response?.result ?? "PENDIENTE"} />
                  </div>
                  {response ? (
                    <p className="control-answer">
                      {response.reason ?? "Sin observaciones adicionales"}
                    </p>
                  ) : inProgress ? (
                    <AuditControlForm
                      busy={busy}
                      canManage={canManage}
                      control={catalogControl}
                      onSubmit={onControl}
                    />
                  ) : null}
                </div>
              );
            })}
            {!availableControls.length ? (
              <EmptyState>
                El catálogo no tiene controles disponibles.
              </EmptyState>
            ) : null}
          </div>
          {inProgress ? (
            <div className="finalize-row">
              <p>
                Finalizar congela los controles. Después podés corregir el
                desvío y generar el PDF desde el dashboard.
              </p>
              <button
                className="button button--dark"
                disabled={
                  busy !== null ||
                  !canManage ||
                  answeredCount !== availableControls.length
                }
                onClick={onFinalize}
                type="button"
              >
                Finalizar auditoría
              </button>
            </div>
          ) : null}
        </Card>
      ) : null}
      {detail.audits.length > 1 ? (
        <p className="history-note">
          Historial: {detail.audits.length} auditorías persistidas en esta obra.
        </p>
      ) : null}
    </section>
  );
}

type AuditResult = "CUMPLE" | "NO_CUMPLE" | "NO_APLICA" | "NO_VERIFICADO";

function AuditControlForm({
  busy,
  canManage,
  control,
  onSubmit,
}: {
  busy: string | null;
  canManage: boolean;
  control: { catalog_code: string; catalog_title: string };
  onSubmit: (event: FormEvent<HTMLFormElement>, catalogCode: string) => void;
}) {
  const [result, setResult] = useState<AuditResult>("CUMPLE");
  const needsReason = result === "NO_APLICA" || result === "NO_VERIFICADO";
  const needsFinding = result === "NO_CUMPLE";

  return (
    <form
      className="audit-form"
      onSubmit={(event) => onSubmit(event, control.catalog_code)}
    >
      <div className="control-prompt">
        <span>{control.catalog_code}</span>
        <strong>Responder control sintético</strong>
      </div>
      <div className="form-grid form-grid--wide">
        <Field label="Resultado">
          <select
            name="result"
            onChange={(event) => setResult(event.target.value as AuditResult)}
            value={result}
          >
            <option>CUMPLE</option>
            <option>NO_CUMPLE</option>
            <option>NO_APLICA</option>
            <option>NO_VERIFICADO</option>
          </select>
        </Field>
        {needsReason ? (
          <Field label="Motivo / observación">
            <input
              name="reason"
              placeholder="Obligatorio para No aplica / No verificado"
              required
            />
          </Field>
        ) : null}
        {needsFinding ? (
          <>
            <Field label="Severidad del desvío">
              <select name="severity_code" defaultValue="MEDIA" required>
                <option>BAJA</option>
                <option>MEDIA</option>
                <option>ALTA</option>
                <option>CRITICA</option>
              </select>
            </Field>
            <Field label="Descripción del desvío">
              <textarea
                name="finding_description"
                placeholder="Requerido cuando el resultado es No cumple"
                required
              />
            </Field>
          </>
        ) : null}
        <button
          className="button button--primary"
          disabled={busy !== null || !canManage}
        >
          Registrar control
        </button>
      </div>
    </form>
  );
}

function FollowupStep({
  detail,
  actor,
  busy,
  canVerify,
  onCorrection,
  onSubmitVerification,
  onVerify,
}: {
  detail: WorksiteDetail;
  actor: PilotActor;
  busy: string | null;
  canVerify: boolean;
  onCorrection: (event: FormEvent<HTMLFormElement>, finding: Finding) => void;
  onSubmitVerification: (finding: Finding) => void;
  onVerify: (event: FormEvent<HTMLFormElement>, finding: Finding) => void;
}) {
  return (
    <section>
      <StepHeading
        eyebrow="08 · Resolución"
        title="Seguimiento y cierre"
        text="La corrección deja evidencia textual sintética y el cierre exige un Responsable H&S independiente."
      />
      {!detail.findings.length ? (
        <EmptyState>
          Los desvíos aparecerán acá cuando un control resulte NO_CUMPLE.
        </EmptyState>
      ) : null}
      <div className="finding-stack">
        {detail.findings.map((finding) => (
          <Card className="finding-card" key={finding.id}>
            <div className="finding-heading">
              <div>
                <div className="badge-row">
                  <StatusBadge value={finding.status} />
                  <StatusBadge value={finding.severity_code} />
                  {finding.overdue ? <StatusBadge value="VENCIDO" /> : null}
                </div>
                <h3>{finding.title || `Desvío ${finding.id.slice(0, 8)}`}</h3>
                <p>{finding.description}</p>
              </div>
              <dl>
                <dt>Plazo</dt>
                <dd>{formatDate(finding.due_at)}</dd>
              </dl>
            </div>
            {finding.status === "ABIERTO" ||
            finding.status === "EN_CORRECCION" ? (
              <form
                className="inline-form"
                onSubmit={(event) => onCorrection(event, finding)}
              >
                <Field label="Corrección aplicada">
                  <textarea
                    name="description"
                    required
                    placeholder="Acción realizada para corregir el desvío"
                  />
                </Field>
                <Field label="Evidencia textual sintética">
                  <textarea
                    name="evidence_note"
                    required
                    placeholder="Qué se verificó, sin adjuntar archivos"
                  />
                </Field>
                <button
                  className="button button--primary"
                  disabled={busy !== null}
                >
                  Agregar corrección
                </button>
              </form>
            ) : null}
            {finding.status === "EN_CORRECCION" &&
            finding.corrections.length ? (
              <button
                className="button button--dark"
                disabled={busy !== null}
                onClick={() => onSubmitVerification(finding)}
                type="button"
              >
                Enviar a verificación
              </button>
            ) : null}
            {finding.status === "PENDIENTE_VERIFICACION" ? (
              <form
                className="verification-form"
                onSubmit={(event) => onVerify(event, finding)}
              >
                <div>
                  <strong>Verificación independiente</strong>
                  <p>
                    El backend impide que creador o corrector se autoverifiquen.
                  </p>
                </div>
                <Field label="Decisión">
                  <select name="decision" defaultValue="ACEPTADA">
                    <option>ACEPTADA</option>
                    <option>RECHAZADA</option>
                  </select>
                </Field>
                <Field label="Fundamento">
                  <input
                    name="notes"
                    required
                    placeholder="Resultado de la revisión"
                  />
                </Field>
                <button
                  className="button button--primary"
                  disabled={busy !== null || !canVerify}
                >
                  Registrar verificación
                </button>
                {!canVerify ? (
                  <small>Cambiá a Responsable H&amp;S.</small>
                ) : null}
              </form>
            ) : null}
            {finding.status === "CERRADO" ? (
              <p className="closed-callout">
                ✓ Desvío cerrado mediante verificación independiente.
              </p>
            ) : null}
            <details className="timeline">
              <summary>Trazabilidad ({finding.events.length} eventos)</summary>
              {finding.events.length ? (
                <ol>
                  {finding.events.map((event) => (
                    <li key={event.id}>
                      <span>{formatDateTime(event.created_at)}</span>
                      <strong>{event.event_type}</strong>
                      <small>
                        {event.from_status ? `${event.from_status} → ` : ""}
                        {event.to_status}
                        {event.actor_id
                          ? ` · ${event.actor_id.slice(0, 8)}`
                          : ""}
                      </small>
                      {event.detail ? <p>{event.detail}</p> : null}
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState>
                  La trazabilidad se completa con cada transición.
                </EmptyState>
              )}
            </details>
            <p className="actor-footnote">Actor actual: {actor}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function StepHeading({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return (
    <div className="section-heading">
      <div>
        <p className="kicker">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      <p>{text}</p>
    </div>
  );
}

function ListHeading({
  count,
  children,
}: {
  count: number;
  children: ReactNode;
}) {
  return (
    <div className="list-heading">
      <h3>{children}</h3>
      <span className="counter">{count}</span>
    </div>
  );
}

function PermissionCopy({
  text = "Cambiá a Técnico o Responsable H&S para editar este bloque.",
}: {
  text?: string;
}) {
  return <p className="permission-note">{text}</p>;
}
