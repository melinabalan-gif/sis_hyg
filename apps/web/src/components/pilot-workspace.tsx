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
  downloadAuditReport,
  formatDate,
  formatDateTime,
  downloadWorksiteReport,
  getWorksite,
  listWorksites,
  pilotLabel,
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
  ["actors", "Actores"],
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
    <span className={`status-badge status-badge--${normalized}`}>
      {pilotLabel(value)}
    </span>
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
  ["OBSERVADO", "Observado"],
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

const CHECKLIST_LABELS: Record<string, string> = {
  brakes: "Frenos",
  lights: "Luces",
  reverse_alarm: "Alarma de retroceso",
  horn: "Bocina",
  tires: "Neumáticos",
  mirrors: "Espejos",
  seat_belt: "Cinturón",
  fire_extinguisher: "Matafuego",
  warning_lights: "Balizas",
  leaks: "Pérdidas",
  guards: "Protecciones",
  signage: "Señalización",
  specific_devices: "Dispositivos específicos",
};

const MACHINE_CHECKLIST_KEYS = Object.keys(CHECKLIST_LABELS);

const FUNCTION_LABELS: Record<string, string> = {
  RESPONSABLE_HYS_PROYECTO: "Licenciado H&S del proyecto",
  AUDITOR: "Auditor",
  RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL:
    "Licenciado H&S de contratista principal",
  TECNICO_HYS_CONTRATISTA_PRINCIPAL: "Técnico H&S de contratista principal",
  RESPONSABLE_HYS_CONTRATISTA: "Licenciado H&S de contratista",
  TECNICO_HYS_CONTRATISTA: "Técnico H&S de contratista",
};

function checklistLabel(key: string): string {
  return CHECKLIST_LABELS[key] ?? pilotLabel(key);
}

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
  const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorksiteDetail | null>(null);
  const [step, setStep] = useState<Step>("overview");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const role = actorRole(actor);
  const actorDefinition = PILOT_ACTORS.find((item) => item.value === actor);
  const canManageResources = role === "TECNICO" || role === "RESPONSABLE_HYS";
  const canManageAssignments = canManageResources;
  const canManageAudit = Boolean(
    detail?.functional_assignments?.some(
      (assignment) =>
        assignment.actor_key === actor &&
        assignment.function_code === "AUDITOR",
    ),
  );
  const canVerify = role === "AUDITOR" || role === "RESPONSABLE_HYS";

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
          setSelectedAuditId(null);
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
    setSelectedAuditId(null);
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
        country: fieldValue(form, "country"),
        province: fieldValue(form, "province"),
        municipality: fieldValue(form, "municipality"),
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

  async function downloadAudit(auditId: string) {
    setBusy("audit-report");
    setError(null);
    setNotice(null);
    try {
      const blob = await downloadAuditReport(auditId, actor);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `auditoria-${auditId.slice(0, 8)}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Informe de auditoría generado desde el historial persistido.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo generar el informe de auditoría.",
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
    if (selectedAuditId) {
      return (
        detail.audits.find((audit) => audit.id === selectedAuditId) ?? null
      );
    }
    return (
      detail.audits.find((audit) => audit.status === "EN_CURSO") ??
      detail.audits.at(-1)!
    );
  }, [detail, selectedAuditId]);

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
              <small>{pilotLabel(worksite.status)}</small>
            </button>
          ))}
        </div>

        <button
          className="button button--primary"
          onClick={() => {
            setSelectedId(null);
            setSelectedAuditId(null);
            setDetail(null);
            setError(null);
            setNotice(null);
          }}
          type="button"
        >
          Nueva obra
        </button>
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
          <div className="actor-context" aria-label="Contexto de asignación">
            <strong>{actorDefinition?.label}</strong>
            <span>
              Profesión:{" "}
              {actorDefinition?.value === "contratista-principal"
                ? "Contratista"
                : actorDefinition?.role === "RESPONSABLE_HYS"
                  ? "Licenciado H&S"
                  : "Técnico H&S"}
            </span>
            <span>
              Empresa representada:{" "}
              {actorDefinition?.role === "TECNICO" ||
              actorDefinition?.value.includes("contratista")
                ? actorDefinition.value === "tecnico" ||
                  actorDefinition.value === "licenciado-contratista-principal"
                  ? "Contratista principal"
                  : "Empresa contratista asignada"
                : actorDefinition?.role === "CONTRATISTA"
                  ? "Cuenta organizacional"
                  : "Proyecto / obra"}
            </span>
            <span>
              Alcance:{" "}
              {actorDefinition?.role === "CONTRATISTA"
                ? "lectura organizacional"
                : "obra seleccionada"}
            </span>
          </div>
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
            <Card className="new-worksite-card">
              <h2>Alta inicial</h2>
              <p className="muted">
                La obra comienza sin actores heredados. Después podrás
                configurar responsables, contratistas y etapas.
              </p>
              <form
                className="form-grid form-grid--wide"
                onSubmit={(event) => void createWorksite(event)}
              >
                <Field label="Código">
                  <input
                    name="code"
                    placeholder="OBRA-001"
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
                <Field label="País">
                  <input
                    name="country"
                    placeholder="Argentina"
                    required
                    maxLength={120}
                  />
                </Field>
                <Field label="Provincia">
                  <input
                    name="province"
                    placeholder="Provincia sintética"
                    required
                    maxLength={120}
                  />
                </Field>
                <Field label="Municipio">
                  <input
                    name="municipality"
                    placeholder="Municipio sintético"
                    required
                    maxLength={120}
                  />
                </Field>
                <button
                  className="button button--primary form-action"
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
            </Card>
          </section>
        ) : (
          <>
            <div className="worksite-titlebar">
              <div>
                <button
                  className="button button--quiet"
                  onClick={() => {
                    setSelectedId(null);
                    setSelectedAuditId(null);
                    setDetail(null);
                    setStep("overview");
                  }}
                  type="button"
                >
                  ← Volver a obras
                </button>
                <p className="kicker">{detail.code}</p>
                <h1>{detail.name}</h1>
              </div>
              <div className="titlebar-meta">
                <span>
                  Ubicación: {detail.country ?? "País no informado"} ·{" "}
                  {detail.province ?? detail.jurisdiction} ·{" "}
                  {detail.municipality ?? "Municipio no informado"}
                </span>
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
                  role={role}
                  onDownloadReport={() => void downloadReport()}
                  onStep={setStep}
                />
              ) : null}
              {step === "actors" ? (
                <ActorsStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageAssignments}
                  onSubmit={(event) =>
                    void submitForm(
                      event,
                      "functional-assignment",
                      `/worksites/${detail.id}/functional-assignments`,
                      (form) => ({
                        actor_id: fieldValue(form, "actor_id"),
                        person_id: fieldValue(form, "person_id"),
                        function_code: fieldValue(form, "function_code"),
                        represented_contractor_id: optionalField(
                          form,
                          "represented_contractor_id",
                        ),
                        valid_from: optionalField(form, "valid_from"),
                      }),
                      "Actor asignado explícitamente a la obra.",
                    )
                  }
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
                  onUpdate={(event, stageId) =>
                    void submitForm(
                      event,
                      `stage-update-${stageId}`,
                      `/worksites/${detail.id}/stages/${stageId}`,
                      (form) => ({
                        status: fieldValue(form, "stage_status"),
                        ended_on: optionalField(form, "stage_ended_on"),
                        notes: optionalField(form, "stage_notes"),
                      }),
                      "Etapa actualizada y cambio trazado.",
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
                        participation_type: optionalField(
                          form,
                          "participation_type",
                        ),
                        parent_contracting_company_id: optionalField(
                          form,
                          "parent_contracting_company_id",
                        ),
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
                        profession_code: fieldValue(form, "profession_code"),
                        contractor_id: fieldValue(form, "contractor_id"),
                        started_on: optionalField(form, "started_on"),
                      }),
                      "Persona sintética asignada al contratista.",
                    )
                  }
                  onVerify={
                    canVerify
                      ? (event, personId) =>
                          void submitForm(
                            event,
                            `person-verification-${personId}`,
                            `/worksites/${detail.id}/people/${personId}/verifications`,
                            (form) => ({
                              status: fieldValue(form, "status"),
                              function_label: fieldValue(
                                form,
                                "function_label",
                              ),
                              observation: optionalField(form, "observation"),
                            }),
                            "Habilitación de persona registrada.",
                          )
                      : undefined
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
                        valid_from: optionalField(form, "version_valid_from"),
                        expires_on: optionalField(form, "version_expires_on"),
                        notes: optionalField(form, "version_notes"),
                      }),
                      "Nueva versión registrada; la vista actual fue actualizada.",
                    )
                  }
                  onReview={
                    canVerify
                      ? (event, documentId) =>
                          void submitForm(
                            event,
                            `document-review-${documentId}`,
                            `/worksites/${detail.id}/documents/${documentId}/reviews`,
                            (form) => ({
                              result: fieldValue(form, "review_result"),
                              foundation: fieldValue(form, "review_foundation"),
                            }),
                            "Revisión documental registrada con fundamento.",
                          )
                      : undefined
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
                        contractor_id: optionalField(form, "contractor_id"),
                        machine_type: optionalField(form, "machine_type"),
                        brand: optionalField(form, "brand"),
                        model: optionalField(form, "model"),
                        license_plate: optionalField(form, "license_plate"),
                        operator_person_id: optionalField(
                          form,
                          "operator_person_id",
                        ),
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
                        checklist: Object.fromEntries(
                          MACHINE_CHECKLIST_KEYS.map((key) => [
                            key,
                            fieldValue(form, key),
                          ]),
                        ),
                        evidence_note: optionalField(form, "evidence_note"),
                      }),
                      "Reinspección registrada; estado y versión actualizados.",
                    )
                  }
                  onValidate={
                    canVerify
                      ? (event, machineId, inspectionId) =>
                          void submitForm(
                            event,
                            `machine-validation-${inspectionId}`,
                            `/worksites/${detail.id}/machines/${machineId}/inspections/${inspectionId}/validations`,
                            (form) => ({
                              notes: fieldValue(form, "validation_notes"),
                            }),
                            "Validación de inspección registrada independientemente.",
                          )
                      : undefined
                  }
                />
              ) : null}
              {step === "audit" ? (
                <AuditStep
                  detail={detail}
                  actor={actor}
                  audit={activeAudit}
                  onSelectAudit={setSelectedAuditId}
                  busy={busy}
                  canManage={canManageAudit}
                  onStart={(assignmentId) => {
                    setSelectedAuditId(null);
                    void mutate(
                      "audit-start",
                      `/worksites/${detail.id}/audits`,
                      assignmentId
                        ? { auditor_assignment_id: assignmentId }
                        : {},
                      "Auditoría iniciada. Ya podés registrar el control.",
                    );
                  }}
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
                        affected_contractor_id: optionalField(
                          form,
                          "affected_contractor_id",
                        ),
                        responsible_contractor_id: optionalField(
                          form,
                          "responsible_contractor_id",
                        ),
                        responsible_person_id: optionalField(
                          form,
                          "responsible_person_id",
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
                  onDownloadReport={(auditId) => void downloadAudit(auditId)}
                  onUnregistered={(event) => {
                    if (!activeAudit) return;
                    void submitForm(
                      event,
                      "unregistered-person-finding",
                      `/audits/${activeAudit.id}/unregistered-people`,
                      (form) => ({
                        description: fieldValue(
                          form,
                          "unregistered_description",
                        ),
                        severity_code: fieldValue(
                          form,
                          "unregistered_severity",
                        ),
                        affected_contractor_id: optionalField(
                          form,
                          "unregistered_contractor_id",
                        ),
                        responsible_contractor_id: optionalField(
                          form,
                          "unregistered_responsible_contractor_id",
                        ),
                      }),
                      "Hallazgo de persona no registrada creado.",
                    );
                  }}
                />
              ) : null}
              {step === "followup" ? (
                <FollowupStep
                  detail={detail}
                  currentActorId={actorDefinition?.id ?? ""}
                  currentActorLabel={
                    actorDefinition?.label ?? "Actor sintético"
                  }
                  busy={busy}
                  canVerify={canVerify}
                  canCorrect={role === "TECNICO" || role === "RESPONSABLE_HYS"}
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
  role,
  onStep,
  onDownloadReport,
}: {
  detail: WorksiteDetail;
  role: string;
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
  const assignments = detail.functional_assignments ?? [];
  const hasPrincipal = detail.contractors.some(
    (item) => item.participation_type === "PRINCIPAL",
  );
  const hasProjectActors = ["RESPONSABLE_HYS_PROYECTO", "AUDITOR"].every(
    (code) => assignments.some((item) => item.function_code === code),
  );
  const totalRecords =
    detail.contractors.length +
    detail.stages.length +
    detail.people.length +
    detail.documents.length +
    detail.machines.length;
  const needsOnboarding = !totalRecords || !hasPrincipal || !hasProjectActors;
  const ratioLabel =
    controls.ratio === null
      ? "Aún no hay auditorías realizadas"
      : `${Math.round(controls.ratio * 100)}%`;
  return (
    <section>
      <div className="section-heading">
        <div>
          <p className="kicker">Estado de la obra</p>
          <h2>
            {role === "AUDITOR"
              ? "Revisión y auditoría"
              : role === "CONTRATISTA"
                ? "Supervisión organizacional"
                : "Recorrido operativo"}
          </h2>
        </div>
        <p>
          Un corte sintético de los registros visibles. Cada panel abre el
          detalle que lo respalda.
        </p>
      </div>
      <p className="dashboard-callout">
        {role === "AUDITOR"
          ? "Priorizá documentación pendiente, habilitaciones y verificaciones."
          : role === "CONTRATISTA"
            ? "Vista de lectura: revisá estado, vencimientos, desvíos y reportes."
            : "Priorizá vencimientos, correcciones y registros pendientes."}
      </p>
      {needsOnboarding ? (
        <Card className="onboarding-card">
          <p className="kicker">Siguiente paso</p>
          <h3>Configurá esta obra antes de operar</h3>
          <p>
            {totalRecords
              ? "Completá las responsabilidades y registros que faltan para que el flujo sea accionable."
              : "La obra está creada sin registros heredados. Seguí este recorrido para preparar un legajo trazable."}
          </p>
          <ol className="onboarding-list">
            <li>
              <button onClick={() => onStep("overview")} type="button">
                Configurar responsables y actores H&amp;S
              </button>
            </li>
            {!hasProjectActors ? (
              <li>
                <button onClick={() => onStep("actors")} type="button">
                  Asignar responsables y Auditor
                </button>
              </li>
            ) : null}
            <li>
              <button onClick={() => onStep("contractors")} type="button">
                Registrar contratista principal
              </button>
            </li>
            <li>
              <button onClick={() => onStep("stages")} type="button">
                Definir etapa inicial
              </button>
            </li>
            <li>
              <button onClick={() => onStep("people")} type="button">
                Incorporar personal
              </button>
            </li>
            <li>
              <button onClick={() => onStep("documents")} type="button">
                Preparar documentación
              </button>
            </li>
          </ol>
        </Card>
      ) : null}
      <div className="metric-grid">
        {quickMetrics.map(([target, label, value], index) => (
          <button key={target} onClick={() => onStep(target)} type="button">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{value}</strong>
            <small>{label}</small>
          </button>
        ))}
      </div>
      <Card className="priority-card">
        <p className="kicker">Prioridades</p>
        <ul className="priority-list">
          {detail.metrics.documents.by_status.VENCIDO ? (
            <li>
              {detail.metrics.documents.by_status.VENCIDO} documento(s)
              vencido(s) requieren acción.
              <button onClick={() => onStep("documents")} type="button">
                Revisar documentación
              </button>
            </li>
          ) : null}
          {detail.metrics.findings.by_status.ABIERTO ||
          detail.metrics.findings.by_status.EN_CORRECCION ? (
            <li>
              {detail.metrics.findings.by_status.ABIERTO +
                detail.metrics.findings.by_status.EN_CORRECCION}{" "}
              desvío(s) abiertos requieren seguimiento.
              <button onClick={() => onStep("followup")} type="button">
                Ver seguimiento
              </button>
            </li>
          ) : null}
          {detail.metrics.findings.by_status.PENDIENTE_VERIFICACION ? (
            <li>
              {detail.metrics.findings.by_status.PENDIENTE_VERIFICACION}{" "}
              corrección(es) esperan verificación.
              <button onClick={() => onStep("followup")} type="button">
                Verificar correcciones
              </button>
            </li>
          ) : null}
          {detail.metrics.machines.by_status.FUERA_DE_SERVICIO ? (
            <li>
              {detail.metrics.machines.by_status.FUERA_DE_SERVICIO}{" "}
              maquinaria(s) fuera de servicio requieren inspección.
              <button onClick={() => onStep("machines")} type="button">
                Revisar maquinarias
              </button>
            </li>
          ) : null}
          {!hasPrincipal || !hasProjectActors ? (
            <li>
              Faltan responsabilidades o contratista principal para operar la
              obra.
              <button
                onClick={() =>
                  onStep(!hasProjectActors ? "actors" : "contractors")
                }
                type="button"
              >
                Completar configuración
              </button>
            </li>
          ) : null}
          {!detail.metrics.documents.by_status.VENCIDO &&
          !detail.metrics.findings.by_status.ABIERTO &&
          !detail.metrics.findings.by_status.EN_CORRECCION &&
          !detail.metrics.findings.by_status.PENDIENTE_VERIFICACION &&
          !detail.metrics.machines.by_status.FUERA_DE_SERVICIO &&
          hasPrincipal &&
          hasProjectActors ? (
            <li>No hay prioridades críticas pendientes en este corte.</li>
          ) : null}
        </ul>
      </Card>
      <Card className="scope-card">
        <div>
          <StatusBadge value="ASIGNACIONES" />
          <h3>Actores y funciones en esta obra</h3>
          <p>
            La profesión, la función operativa, la empresa representada y el
            alcance se mantienen separados.
          </p>
        </div>
        <ul className="record-list">
          {(detail.functional_assignments ?? []).map((assignment) => (
            <li key={assignment.id}>
              <div>
                <strong>{assignment.actor_label}</strong>
                <span>
                  {pilotLabel(assignment.function_code)} ·{" "}
                  {pilotLabel(assignment.profession_code)}
                </span>
              </div>
              <small>
                {assignment.represented_contractor_name ?? "Proyecto / obra"} ·{" "}
                {assignment.permission_scope === "ORGANIZATION"
                  ? "Organización"
                  : "Obra seleccionada"}
              </small>
            </li>
          ))}
        </ul>
      </Card>
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
              <strong>{pilotLabel(latestAudit.status)}</strong>
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
              <span>Resultado de controles evaluados</span>
              <strong>{ratioLabel}</strong>
            </div>
            <p>
              {controls.numerator} cumplen / {controls.denominator} evaluados
            </p>
          </div>
          <p className="dashboard-legend">
            Excluye &quot;No aplica&quot; ({controls.excluded.no_aplica}) y
            &quot;No verificado&quot; ({controls.excluded.no_verificado}). Sólo
            usa controles registrados de la última auditoría visible.
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
            Este corte llega hasta una auditoría <strong>finalizada</strong> y
            un desvío <strong>cerrado</strong> por un Responsable H&amp;S
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

function ActorsStep({ detail, busy, canManage, onSubmit }: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="02 · Alcance profesional"
        title="Actores y funciones de esta obra"
        text="Las asignaciones son explícitas: persona, función, empresa representada y alcance. Una obra nueva no hereda profesionales."
      />
      <div className="two-column">
        <Card>
          <h3>Asignar actor profesional</h3>
          <form className="form-grid" onSubmit={onSubmit}>
            <Field label="Identidad sintética">
              <select name="actor_id" required defaultValue="">
                <option value="" disabled>
                  Seleccionar identidad…
                </option>
                {PILOT_ACTORS.filter((item) => item.role !== "CONTRATISTA").map(
                  (item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ),
                )}
              </select>
            </Field>
            <Field label="Persona profesional">
              <select name="person_id" required defaultValue="">
                <option value="" disabled>
                  Seleccionar persona…
                </option>
                {detail.people
                  .filter((item) =>
                    ["LICENCIADO_HYS", "TECNICO_HYS"].includes(
                      item.profession_code ?? "",
                    ),
                  )
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name} · {pilotLabel(item.profession_code)}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Función en la obra">
              <select name="function_code" required defaultValue="">
                <option value="" disabled>
                  Seleccionar función…
                </option>
                {Object.entries(FUNCTION_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Empresa representada">
              <select name="represented_contractor_id" defaultValue="">
                <option value="">Proyecto / obra</option>
                {detail.contractors.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.legal_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Vigente desde (opcional)">
              <input name="valid_from" type="date" />
            </Field>
            <button
              className="button button--primary form-action"
              disabled={busy !== null || !canManage || !detail.people.length}
            >
              Asignar función
            </button>
          </form>
          {!detail.people.length ? (
            <p className="permission-note">
              Primero registrá la persona profesional en Personal.
            </p>
          ) : null}
          {!canManage ? (
            <PermissionCopy text="Cambiá a Técnico o Responsable H&S para configurar actores." />
          ) : null}
        </Card>
        <Card>
          <ListHeading count={detail.functional_assignments?.length ?? 0}>
            Asignaciones vigentes e históricas
          </ListHeading>
          {detail.functional_assignments?.length ? (
            <ul className="record-list">
              {detail.functional_assignments.map((assignment) => (
                <li key={assignment.id}>
                  <div>
                    <strong>
                      {assignment.person_name ?? assignment.actor_label}
                    </strong>
                    <span>
                      {FUNCTION_LABELS[assignment.function_code] ??
                        pilotLabel(assignment.function_code)}
                    </span>
                  </div>
                  <small>
                    {assignment.represented_contractor_name ??
                      "Proyecto / obra"}{" "}
                    ·{" "}
                    {assignment.permission_scope === "ORGANIZATION"
                      ? "Organización"
                      : "Obra seleccionada"}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Todavía no hay actores asignados.</EmptyState>
          )}
        </Card>
      </div>
    </section>
  );
}

function StagesStep({
  detail,
  busy,
  canManage,
  onSubmit,
  onUpdate,
}: StepProps) {
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
              <select name="name" defaultValue="Preparación">
                {[
                  "Preparación",
                  "Montaje",
                  "Demolición",
                  "Excavación",
                  "Submuración",
                  "Fundaciones",
                  "Estructura",
                  "Albañilería",
                  "Instalaciones",
                  "Terminaciones",
                  "Cierre",
                ].map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
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
                      <StatusBadge value={stage.status ?? "ACTIVA"} />
                      <small>
                        {formatDate(stage.started_on)} —{" "}
                        {formatDate(stage.ended_on)}
                      </small>
                    </div>
                    <strong>{stage.name}</strong>
                    {stage.sector ? <span>Sector: {stage.sector}</span> : null}
                    {stage.notes ? <p>{stage.notes}</p> : null}
                    {stage.history?.length ? (
                      <details className="inline-history">
                        <summary>
                          {stage.history.length} cambios trazados
                        </summary>
                        <ol>
                          {stage.history.map((event) => (
                            <li key={event.id}>
                              {formatDateTime(event.created_at)} ·{" "}
                              {pilotLabel(event.event_type)}
                              {event.detail ? ` · ${event.detail}` : ""}
                            </li>
                          ))}
                        </ol>
                      </details>
                    ) : null}
                    {onUpdate ? (
                      <details>
                        <summary>Actualizar etapa</summary>
                        <form
                          className="inline-form"
                          onSubmit={(event) => onUpdate(event, stage.id)}
                        >
                          <select
                            name="stage_status"
                            defaultValue={stage.status ?? "ACTIVA"}
                          >
                            <option value="PLANIFICADA">Planificada</option>
                            <option value="ACTIVA">Activa</option>
                            <option value="CERRADA">Cerrada</option>
                          </select>
                          <input
                            name="stage_ended_on"
                            type="date"
                            defaultValue={stage.ended_on ?? ""}
                          />
                          <input
                            name="stage_notes"
                            placeholder="Nota del cambio"
                          />
                          <button
                            className="button button--dark"
                            disabled={busy !== null || !canManage}
                          >
                            Actualizar
                          </button>
                        </form>
                      </details>
                    ) : null}
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
  onValidate?: (
    event: FormEvent<HTMLFormElement>,
    machineId: string,
    inspectionId: string,
  ) => void;
  onVerify?: (event: FormEvent<HTMLFormElement>, personId: string) => void;
  onReview?: (event: FormEvent<HTMLFormElement>, documentId: string) => void;
  onUpdate?: (event: FormEvent<HTMLFormElement>, stageId: string) => void;
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
            <Field label="Participación">
              <select name="participation_type" defaultValue="">
                <option value="">Automática</option>
                <option value="PRINCIPAL">Principal</option>
                <option value="CONTRACTOR">Contratista</option>
              </select>
            </Field>
            <Field label="Empresa contratante (opcional)">
              <select name="parent_contracting_company_id" defaultValue="">
                <option value="">Sin empresa</option>
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
                    <small>
                      {pilotLabel(item.participation_type ?? "CONTRACTOR")}
                      {item.parent_contracting_company_name
                        ? ` · Depende de ${item.parent_contracting_company_name}`
                        : " · Sin empresa contratante"}
                    </small>
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

function PeopleStep({
  detail,
  busy,
  canManage,
  onSubmit,
  onVerify,
}: StepProps) {
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
            <Field label="Profesión controlada">
              <select name="profession_code" defaultValue="OTRA">
                <option value="LICENCIADO_HYS">Licenciado H&amp;S</option>
                <option value="TECNICO_HYS">Técnico H&amp;S</option>
                <option value="CONTRATISTA">Contratista</option>
                <option value="OTRA">Otra</option>
              </select>
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
                    <span>
                      {item.role_label} · Profesión{" "}
                      {pilotLabel(item.profession_code ?? "OTRA")}
                    </span>
                  </div>
                  <small>
                    {item.contractor_name ??
                      detail.contractors.find(
                        (contractor) => contractor.id === item.contractor_id,
                      )?.legal_name ??
                      "Contratista asignado"}
                  </small>
                  <StatusBadge
                    value={item.habilitation_status ?? "PENDIENTE_VERIFICACION"}
                  />
                  {onVerify ? (
                    <form
                      className="inline-form"
                      onSubmit={(event) => onVerify(event, item.id)}
                    >
                      <select name="status" defaultValue="HABILITADO">
                        <option value="HABILITADO">Habilitado</option>
                        <option value="DOCUMENTACION_INCOMPLETA">
                          Documentación incompleta
                        </option>
                        <option value="NO_HABILITADO">No habilitado</option>
                      </select>
                      <input
                        name="function_label"
                        required
                        placeholder="Función verificadora"
                      />
                      <input
                        name="observation"
                        placeholder="Fundamento u observación"
                      />
                      <button
                        className="button button--dark"
                        disabled={busy !== null}
                      >
                        Verificar
                      </button>
                    </form>
                  ) : null}
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
  onReview,
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
          <p className="permission-note">
            Todo documento nuevo queda pendiente hasta una revisión separada.
          </p>
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
                <dd>{pilotLabel(item.review_status)}</dd>
              </div>
              <div>
                <dt>Vencimiento</dt>
                <dd>{formatDate(item.expires_on)}</dd>
              </div>
            </dl>
            <p className="muted">
              Cargado por {item.uploaded_by?.slice(0, 8) ?? "actor sintético"}
              {item.uploaded_at ? ` · ${formatDateTime(item.uploaded_at)}` : ""}
            </p>
            {item.reviews?.length ? (
              <details className="document-history">
                <summary>Revisiones ({item.reviews.length})</summary>
                <ul className="document-history__list">
                  {item.reviews.map((review) => (
                    <li key={review.id}>
                      <strong>{pilotLabel(review.result)}</strong>
                      <span>{review.foundation}</span>
                      <small>
                        {review.reviewer_function} ·{" "}
                        {formatDateTime(review.reviewed_at)}
                      </small>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
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
                          {version.document_type} ·{" "}
                          {pilotLabel(version.review_status)}
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
                  <p className="permission-note">
                    La nueva versión también requiere revisión independiente.
                  </p>
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
            {onReview ? (
              <details className="document-version-form">
                <summary>Revisar documento</summary>
                <form
                  className="form-grid form-grid--wide"
                  onSubmit={(event) => onReview(event, item.id)}
                >
                  <Field label="Resultado">
                    <select name="review_result" defaultValue="APROBADO">
                      <option value="APROBADO">Aprobado</option>
                      <option value="OBSERVADO">Observado</option>
                      <option value="RECHAZADO">Rechazado</option>
                    </select>
                  </Field>
                  <Field label="Fundamento">
                    <textarea name="review_foundation" required />
                  </Field>
                  <button
                    className="button button--dark form-action"
                    disabled={busy !== null}
                  >
                    Registrar revisión
                  </button>
                </form>
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
  onValidate,
}: StepProps) {
  return (
    <section>
      <StepHeading
        eyebrow="06 · Activos"
        title="Maquinarias"
        text="El alta administrativa del equipo está separada de la inspección técnica. Cada inspección conserva actor, función, checklist y evidencia."
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
            <Field label="Tipo de máquina">
              <input name="machine_type" placeholder="Autoelevador" />
            </Field>
            <Field label="Marca y modelo">
              <input name="brand" placeholder="Marca sintética" />
            </Field>
            <Field label="Modelo">
              <input name="model" placeholder="Modelo sintético" />
            </Field>
            <Field label="Patente o identificación">
              <input name="license_plate" placeholder="SINT-001" />
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
            <Field label="Operador asignado (opcional)">
              <select name="operator_person_id" defaultValue="">
                <option value="">Sin operador asignado</option>
                {detail.people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
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
                      Fuera de servicio: no debe operar hasta una inspección que
                      documente el levantamiento de la condición.
                    </p>
                  ) : null}
                  {!item.inspections?.length ? (
                    <p className="permission-note">
                      Alta administrativa registrada. Falta la primera
                      inspección técnica.
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
                            {inspection.checklist ? (
                              <small>
                                Checklist:{" "}
                                {Object.entries(inspection.checklist)
                                  .map(
                                    ([key, value]) =>
                                      `${checklistLabel(key)}: ${pilotLabel(value)}`,
                                  )
                                  .join(" · ")}
                              </small>
                            ) : null}
                            {inspection.validations?.map((validation) => (
                              <small key={validation.id}>
                                Validada por {validation.validator_function} ·{" "}
                                {formatDateTime(validation.validated_at)}
                              </small>
                            ))}
                            {onValidate ? (
                              <form
                                className="inline-form"
                                onSubmit={(event) =>
                                  onValidate(event, item.id, inspection.id)
                                }
                              >
                                <input
                                  name="validation_notes"
                                  required
                                  placeholder="Notas de validación"
                                />
                                <button
                                  className="button button--dark"
                                  disabled={busy !== null}
                                >
                                  Validar inspección
                                </button>
                              </form>
                            ) : null}
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
                            <option value="OPERATIVA">Operativa</option>
                            <option value="CON_OBSERVACIONES">
                              Con observaciones
                            </option>
                            <option value="FUERA_DE_SERVICIO">
                              Fuera de servicio
                            </option>
                          </select>
                        </Field>
                        <Field label="Motivo de reinspección">
                          <textarea
                            name="inspection_reason"
                            placeholder="Describí el resultado y la causa de la transición"
                            required
                          />
                        </Field>
                        {MACHINE_CHECKLIST_KEYS.map((key) => (
                          <Field key={key} label={checklistLabel(key)}>
                            <select name={key} defaultValue="CUMPLE">
                              <option value="CUMPLE">Cumple</option>
                              <option value="NO_CUMPLE">No cumple</option>
                              <option value="NO_APLICA">No aplica</option>
                              <option value="NO_VERIFICADO">
                                No verificado
                              </option>
                            </select>
                          </Field>
                        ))}
                        <Field label="Evidencia o referencia">
                          <input
                            name="evidence_note"
                            placeholder="Referencia sintética"
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
  actor,
  audit,
  busy,
  canManage,
  onStart,
  onSelectAudit,
  onControl,
  onFinalize,
  onDownloadReport,
  onUnregistered,
}: {
  detail: WorksiteDetail;
  actor: PilotActor;
  audit: Audit | null;
  busy: string | null;
  canManage: boolean;
  onStart: (assignmentId?: string) => void;
  onSelectAudit: (auditId: string) => void;
  onControl: (event: FormEvent<HTMLFormElement>, catalogCode: string) => void;
  onFinalize: () => void;
  onDownloadReport: (auditId: string) => void;
  onUnregistered: (event: FormEvent<HTMLFormElement>) => void;
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
  const auditAssignments = (detail.functional_assignments ?? []).filter(
    (assignment) =>
      assignment.actor_key === actor && assignment.function_code === "AUDITOR",
  );
  const [selectedAssignmentId, setSelectedAssignmentId] = useState(
    auditAssignments[0]?.id ?? "",
  );
  return (
    <section>
      <StepHeading
        eyebrow="07 · Campo"
        title="Auditoría"
        text="El checklist es sintético y online. Un resultado no conforme crea el desvío de forma atómica."
      />
      {!audit || audit.status === "FINALIZADA" ? (
        <Card className="action-card">
          <div>
            <h3>Iniciar una auditoría</h3>
            <p>Fija obra, auditoría asignada y catálogo sintético publicado.</p>
          </div>
          {auditAssignments.length ? (
            <Field label="Asignación de auditoría">
              <select
                aria-label="Asignación de auditoría"
                onChange={(event) =>
                  setSelectedAssignmentId(event.target.value)
                }
                value={selectedAssignmentId}
              >
                {auditAssignments.map((assignment) => (
                  <option key={assignment.id} value={assignment.id}>
                    {pilotLabel(assignment.function_code)} ·{" "}
                    {assignment.person_name ?? assignment.actor_label}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          <button
            className="button button--primary"
            disabled={busy !== null || !canManage}
            onClick={() => onStart(selectedAssignmentId || undefined)}
            type="button"
          >
            Iniciar auditoría
          </button>
        </Card>
      ) : null}
      {detail.audits.length ? (
        <Card>
          <ListHeading count={detail.audits.length}>
            Historial de auditorías
          </ListHeading>
          <div className="audit-history-list">
            {detail.audits.map((item) => (
              <button
                className={item.id === audit?.id ? "is-active" : ""}
                key={item.id}
                onClick={() => onSelectAudit(item.id)}
                type="button"
              >
                <strong>Auditoría {item.id.slice(0, 8)}</strong>
                <span>{formatDateTime(item.started_at)}</span>
                <small>
                  {pilotLabel(item.auditor_function)} ·{" "}
                  {pilotLabel(item.status)}
                </small>
              </button>
            ))}
          </div>
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
          <dl className="compact-details audit-details">
            <div>
              <dt>Auditor</dt>
              <dd>{audit.auditor_name ?? "Sin informar"}</dd>
            </div>
            <div>
              <dt>Función</dt>
              <dd>{pilotLabel(audit.auditor_function)}</dd>
            </div>
            <div>
              <dt>Responsable asociado</dt>
              <dd>{audit.responsible_professional_name ?? "Sin informar"}</dd>
            </div>
          </dl>
          <button
            className="button button--dark"
            disabled={busy !== null}
            onClick={() => onDownloadReport(audit.id)}
            type="button"
          >
            Descargar informe de auditoría
          </button>
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
                      contractors={detail.contractors}
                      people={detail.people}
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
            <form className="inline-form" onSubmit={onUnregistered}>
              <input
                name="unregistered_description"
                required
                placeholder="Describí la persona no registrada"
              />
              <select name="unregistered_severity" defaultValue="MEDIA">
                <option value="BAJA">Baja</option>
                <option value="MEDIA">Media</option>
                <option value="ALTA">Alta</option>
                <option value="CRITICA">Crítica</option>
              </select>
              <select name="unregistered_contractor_id" defaultValue="">
                <option value="">Empresa afectada (opcional)</option>
                {detail.contractors.map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.legal_name}
                  </option>
                ))}
              </select>
              <select
                name="unregistered_responsible_contractor_id"
                defaultValue=""
              >
                <option value="">Responsable de corregir (opcional)</option>
                {detail.contractors.map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.legal_name}
                  </option>
                ))}
              </select>
              <button className="button button--dark" disabled={busy !== null}>
                Registrar persona no registrada
              </button>
            </form>
          ) : null}
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
  contractors,
  people,
  onSubmit,
}: {
  busy: string | null;
  canManage: boolean;
  control: { catalog_code: string; catalog_title: string };
  contractors: WorksiteDetail["contractors"];
  people: WorksiteDetail["people"];
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
            <option value="CUMPLE">Cumple</option>
            <option value="NO_CUMPLE">No cumple</option>
            <option value="NO_APLICA">No aplica</option>
            <option value="NO_VERIFICADO">No verificado</option>
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
            <Field label="Empresa afectada (opcional)">
              <select name="affected_contractor_id" defaultValue="">
                <option value="">Sin empresa determinada</option>
                {contractors.map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.legal_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Responsable de corregir (empresa)">
              <select name="responsible_contractor_id" defaultValue="">
                <option value="">Usar empresa afectada</option>
                {contractors.map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.legal_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Responsable de corregir (persona)">
              <select name="responsible_person_id" defaultValue="">
                <option value="">Sin persona específica</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
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
  currentActorId,
  currentActorLabel,
  busy,
  canVerify,
  canCorrect,
  onCorrection,
  onSubmitVerification,
  onVerify,
}: {
  detail: WorksiteDetail;
  currentActorId: string;
  currentActorLabel: string;
  busy: string | null;
  canVerify: boolean;
  canCorrect: boolean;
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
          Los desvíos aparecerán acá cuando un control resulte no conforme.
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
                <dl className="finding-details">
                  <div>
                    <dt>Origen</dt>
                    <dd>{finding.source_label ?? "Hallazgo manual"}</dd>
                  </div>
                  <div>
                    <dt>Auditoría</dt>
                    <dd>{finding.audit_id.slice(0, 8)}</dd>
                  </div>
                  <div>
                    <dt>Detectado</dt>
                    <dd>{formatDateTime(finding.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Afectado</dt>
                    <dd>
                      {finding.affected_contractor_name ??
                        "Sin empresa asignada"}
                    </dd>
                  </div>
                  <div>
                    <dt>Responsable de corregir</dt>
                    <dd>
                      {finding.responsible_person_name ??
                        finding.responsible_contractor_name ??
                        "Sin responsable asignado"}
                    </dd>
                  </div>
                </dl>
              </div>
              <dl>
                <dt>Plazo</dt>
                <dd>{formatDate(finding.due_at)}</dd>
              </dl>
            </div>
            {canCorrect &&
            (finding.status === "ABIERTO" ||
              finding.status === "EN_CORRECCION") ? (
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
            {canCorrect &&
            finding.status === "EN_CORRECCION" &&
            finding.corrections.at(-1)?.created_by === currentActorId ? (
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
            {finding.corrections.length ? (
              <div className="finding-history-block">
                <h4>Correcciones y evidencias</h4>
                <ol className="finding-history-list">
                  {finding.corrections.map((correction) => (
                    <li key={correction.id}>
                      <strong>{correction.description}</strong>
                      <span>{correction.evidence_note}</span>
                      <small>
                        Informada por{" "}
                        {correction.created_by?.slice(0, 8) ??
                          "actor sintético"}{" "}
                        · {formatDateTime(correction.created_at)}
                      </small>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
            {finding.verifications.length ? (
              <div className="finding-history-block">
                <h4>Decisiones de verificación</h4>
                <ol className="finding-history-list">
                  {finding.verifications.map((verification) => (
                    <li key={verification.id}>
                      <strong>{pilotLabel(verification.decision)}</strong>
                      <span>{verification.notes}</span>
                      <small>
                        Por{" "}
                        {verification.verified_by?.slice(0, 8) ??
                          "actor sintético"}{" "}
                        · {formatDateTime(verification.created_at)}
                      </small>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
            <details className="timeline">
              <summary>Trazabilidad ({finding.events.length} eventos)</summary>
              {finding.events.length ? (
                <ol>
                  {finding.events.map((event) => (
                    <li key={event.id}>
                      <span>{formatDateTime(event.created_at)}</span>
                      <strong>{pilotLabel(event.event_type)}</strong>
                      <small>
                        {event.from_status
                          ? `${pilotLabel(event.from_status)} → `
                          : ""}
                        {pilotLabel(event.to_status)}
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
            <p className="actor-footnote">Actor actual: {currentActorLabel}</p>
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
