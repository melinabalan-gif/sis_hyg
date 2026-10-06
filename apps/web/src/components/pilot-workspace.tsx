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
  getWorksite,
  listWorksites,
  pilotLabel,
  type Audit,
  type Finding,
  type PilotActor,
  type WorksiteDetail,
  type WorksiteSummary,
  postPilot,
} from "../lib/pilot-api";

const STEPS = [
  ["overview", "Inicio"],
  ["actors", "Responsables"],
  ["stages", "Etapas"],
  ["contractors", "Contratistas"],
  ["people", "Personal"],
  ["documents", "Legajos Técnicos"],
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

const WORKSITE_CREATOR_ACTORS: readonly PilotActor[] = [
  "responsable",
  "licenciado-contratista-principal",
  "contratista-principal",
];

const PRINCIPAL_TECHNICAL_FILE_EDITORS: readonly PilotActor[] = [
  "tecnico",
  "licenciado-contratista-principal",
];

const PRINCIPAL_TECHNICAL_FILE_LICENSED_ONLY = new Set([
  "Matrícula del Licenciado H&S responsable",
  "Carga horaria semanal",
]);

const PROJECT_TECHNICAL_FILE_EDITORS: readonly PilotActor[] = ["responsable"];

function checklistLabel(key: string): string {
  return CHECKLIST_LABELS[key] ?? pilotLabel(key);
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
  const canCreateWorksite = WORKSITE_CREATOR_ACTORS.includes(actor);
  const canManageAssignments =
    actor === "responsable" || actor === "contratista-principal";
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
name: fieldValue(form, "name"),
address: fieldValue(form, "address"),
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

  return (
    <div className="pilot-layout">
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>
      <aside className="worksite-rail" aria-label="Navegación principal">
        <div className="rail-brand">
          <svg
              className="brand-symbol"
              viewBox="0 0 40 40"
              aria-hidden="true"
            >
              <path className="brand-symbol__h" d="M7 7v26M18 7v26M7 20h11" />
              <path
                className="brand-symbol__s"
                d="M32 10c-2-2.2-4.3-3.2-7-3.2-3.8 0-6.3 1.9-6.3 4.9 0 3.1 2.7 4.1 6.3 5.2 3.8 1.1 6.6 2.4 6.6 6.4 0 4.1-3.3 7-8.1 7-3.5 0-6.5-1.3-8.7-3.8"
              />
            </svg>
          <span>
            <strong>H&amp;S Gestión</strong>
            <small>Piloto operativo</small>
          </span>
        </div>
        <button
          className={`rail-home ${!selectedId ? "is-active" : ""}`}
          onClick={() => {
            setSelectedId(null);
            setSelectedAuditId(null);
            setDetail(null);
            setStep("overview");
          }}
          type="button"
        >
          <span aria-hidden="true">OB</span>
          Obras
        </button>

        {selectedId && detail ? (
          <nav
            className="worksite-nav"
            aria-label="Navegación de la obra activa"
          >
            <div className="worksite-nav__heading">
              <div>
                <p className="kicker">Obra activa</p>
                <strong>{detail.name}</strong>
                <small>
                  {detail.code} · {pilotLabel(detail.status)}
                </small>
              </div>
            </div>
            <p className="worksite-nav__label">Módulos de la obra</p>
            <div
              className="worksite-nav__items"
              role="tablist"
              aria-label="Módulos de la obra"
            >
              {STEPS.map(([value, label]) => (
                <button
                  aria-controls={`panel-${value}`}
                  aria-selected={step === value}
                  className={step === value ? "is-active" : ""}
                  id={`tab-${value}`}
                  key={value}
                  onClick={() => setStep(value)}
                  role="tab"
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
          </nav>
        ) : null}
      </aside>

      <section
        className="workspace"
        id="main-content"
        aria-label="Espacio de trabajo de la obra"
        aria-busy={loading}
        tabIndex={-1}
      >
        <header className="workspace-header">
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
          <div className="actor-context" aria-label="Perfil activo">
            <strong>{actorDefinition?.label}</strong>
            <span>Perfil operativo del piloto</span>
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
            <p className="kicker">Punto de partida</p>
            <h1>
              {canCreateWorksite
                ? "Creá o abrí una obra"
                : "Abrí una obra existente"}
            </h1>
            <p>
              {canCreateWorksite
                ? "Seleccioná una obra o creá una nueva para iniciar el piloto."
                : "Seleccioná una obra para iniciar el recorrido operativo."}
            </p>
            {worksites.length ? (
              <div className="central-worksite-list">
                <h2 className="kicker">Obras disponibles</h2>
                {worksites.map((worksite) => (
                  <button
                    className="central-worksite-button"
                    key={worksite.id}
                    onClick={() => void selectWorksite(worksite.id)}
                    type="button"
                  >
                    <span>
                      <strong>{worksite.name}</strong>
                      <small>
                        {worksite.code} · {pilotLabel(worksite.status)}
                      </small>
                    </span>
                    <span aria-hidden="true">→</span>
                  </button>
                ))}
              </div>
            ) : null}
            {canCreateWorksite ? (
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
                  <Field label="Nombre de fantasía">
                    <input
                      name="name"
                      placeholder="Ampliación planta piloto"
                      required
                      maxLength={200}
                    />
                  </Field>
                <Field label="Dirección">
                  <input
                    name="address"
                    placeholder="Ej. Ayacucho 1250"
                    required
                    maxLength={240}
                  />
                </Field>
                  <button
                    className="button button--primary form-action"
                    disabled={busy !== null}
                  >
                    {busy === "worksite" ? "Creando…" : "Crear y abrir"}
                  </button>
                </form>
              </Card>
            ) : null}
          </section>
        ) : (
          <>
            <div className="worksite-titlebar">
              <div className="worksite-titlebar__identity">
                <button
                  className="button button--quiet back-button"
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
                {step === "overview" ? (
                  <>
                    <p className="kicker">Inicio</p>
                    <h1>Inicio</h1>
                  </>
                ) : null}
              </div>
            </div>

            <div
              className="step-content"
              id={`panel-${step}`}
              aria-labelledby={`tab-${step}`}
              role="tabpanel"
              tabIndex={0}
            >
              {step === "overview" ? (
                <Overview detail={detail} actor={actor} onStep={setStep} />
              ) : null}
              {step === "actors" ? (
                <ResponsablesStep
                  detail={detail}
                  busy={busy}
                  canManage={canManageAssignments}
                  onAssign={(event, functionCode, currentId) => {
                    const path = currentId
                      ? `/worksites/${detail.id}/functional-assignments/${currentId}/change`
                      : `/worksites/${detail.id}/functional-assignments`;
                    void submitForm(
                      event,
                      `functional-assignment-${functionCode}`,
                      path,
                      (form) => {
                        const personId = fieldValue(form, "person_id");
                        const person = detail.people.find(
                          (item) => item.id === personId,
                        );
                        const actorId =
                          functionCode === "AUDITOR"
                            ? person?.profession_code === "TECNICO_HYS"
                              ? PILOT_ACTORS.find(
                                  (item) => item.value === "auditor",
                                )?.id
                              : PILOT_ACTORS.find(
                                  (item) => item.value === "responsable",
                                )?.id
                            : functionCode === "RESPONSABLE_HYS_PROYECTO"
                              ? PILOT_ACTORS.find(
                                  (item) => item.value === "responsable",
                                )?.id
                              : functionCode ===
                                  "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL"
                                ? PILOT_ACTORS.find(
                                    (item) =>
                                      item.value ===
                                      "licenciado-contratista-principal",
                                  )?.id
                                : PILOT_ACTORS.find(
                                    (item) => item.value === "tecnico",
                                  )?.id;
                        const payload: Record<string, unknown> = {
                          actor_id: actorId,
                          person_id: personId,
                        };
                        if (!currentId) {
                          payload.function_code = functionCode;
                          if (
                            functionCode ===
                              "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL" ||
                            functionCode === "TECNICO_HYS_CONTRATISTA_PRINCIPAL"
                          ) {
                            payload.represented_contractor_id =
                              detail.contractors.find(
                                (item) =>
                                  item.participation_type === "PRINCIPAL",
                              )?.id;
                          }
                        }
                        if (functionCode === "AUDITOR") {
                          payload.delegated_by_assignment_id = optionalField(
                            form,
                            "delegated_by_assignment_id",
                          );
                        }
                        return payload;
                      },
                      currentId
                        ? "Responsable cambiado y asignación anterior conservada en el historial."
                        : "Responsable asignado a la obra.",
                    );
                  }}
                  onFinish={(assignmentId) => {
                    void mutate(
                      `functional-assignment-finish-${assignmentId}`,
                      `/worksites/${detail.id}/functional-assignments/${assignmentId}/finish`,
                      {},
                      "Responsable finalizado y conservado en el historial.",
                    );
                  }}
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
                <DocumentsStep detail={detail} actor={actor} />
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
  actor,
  onStep,
}: {
  detail: WorksiteDetail;
  actor: PilotActor;
  onStep: (step: Step) => void;
}) {
  const assignments = detail.functional_assignments ?? [];

  const hasPrincipal = detail.contractors.some(
    (item) => item.participation_type === "PRINCIPAL",
  );

  const hasProjectResponsible = assignments.some(
    (item) => item.function_code === "RESPONSABLE_HYS_PROYECTO",
  );

  const hasAuditor = assignments.some(
    (item) => item.function_code === "AUDITOR",
  );

  const hasStages = detail.stages.length > 0;

  const hasProjectFile = detail.documents.some(
    (item) =>
      item.subject_kind === "WORKSITE" &&
      item.subject_id === detail.id,
  );

  const pendingDocuments =
    detail.metrics.documents.by_status.FALTANTE +
    detail.metrics.documents.by_status.PENDIENTE +
    detail.metrics.documents.by_status.RECHAZADO +
    detail.metrics.documents.by_status.POR_VENCER +
    detail.metrics.documents.by_status.VENCIDO;

  const openFindings =
    detail.metrics.findings.by_status.ABIERTO +
    detail.metrics.findings.by_status.PENDIENTE_VERIFICACION;

  const machineIssues =
    detail.metrics.machines.by_status.FUERA_DE_SERVICIO +
    detail.metrics.machines.by_status.CON_OBSERVACIONES;

  const hasOperationalActivity =
    detail.people.length > 0 ||
    detail.metrics.findings.total > 0 ||
    detail.metrics.machines.total > 0 ||
    detail.metrics.latest_audit !== null ||
    detail.contractors.some(
      (item) => item.participation_type !== "PRINCIPAL",
    );

  if (!hasOperationalActivity) {
    const setupItems: {
      label: string;
      status: string;
      ready: boolean;
      step: Step;
      action: string;
      visible: boolean;
    }[] = [
      {
        label: "Responsable H&S del proyecto",
        status: hasProjectResponsible ? "Configurado" : "Falta configurar",
        ready: hasProjectResponsible,
        step: "actors",
        action: "Configurar",
        visible: actor === "responsable" || actor === "contratista-principal",
      },
      {
        label: "Contratista principal",
        status: hasPrincipal ? "Registrado" : "Sin registrar",
        ready: hasPrincipal,
        step: "contractors",
        action: "Registrar",
        visible:
          actor === "responsable" ||
          actor === "licenciado-contratista-principal" ||
          actor === "tecnico" ||
          actor === "contratista-principal",
      },
      {
        label: "Etapas de obra",
        status: hasStages ? "Definidas" : "Sin definir",
        ready: hasStages,
        step: "stages",
        action: "Definir etapas",
        visible:
          actor === "responsable" ||
          actor === "licenciado-contratista-principal" ||
          actor === "tecnico",
      },
      {
        label: "Legajo Técnico de Proyecto",
        status: hasProjectFile ? "Iniciado" : "Sin completar",
        ready: hasProjectFile,
        step: "documents",
        action: "Abrir legajo",
        visible: actor === "responsable",
      },
      {
        label: "Auditor",
        status: hasAuditor ? "Asignado" : "Sin asignar",
        ready: hasAuditor,
        step: "actors",
        action: "Asignar",
        visible: actor === "responsable",
      },
    ];

    return (
      <section className="overview-screen">
        <Card className="priority-card primary-actions-card">
          <div className="dashboard-panel__header">
            <div>
              <p className="kicker">Puesta en marcha</p>
              <h2>Prepará la obra para comenzar</h2>
            </div>
          </div>

          <p className="muted">
            Completá la configuración inicial necesaria para comenzar la gestión
            operativa de la obra.
          </p>

          <div className="action-grid">
            {setupItems.map((item) => (
              <div className="action-tile" key={item.label}>
                <span className="action-tile__copy">
                  <strong>{item.label}</strong>
                  <small>{item.status}</small>
                </span>

                {!item.ready && item.visible ? (
                  <button
                    className="button button--quiet"
                    onClick={() => onStep(item.step)}
                    type="button"
                  >
                    {item.action} →
                  </button>
                ) : (
                  <span className={item.ready ? "setup-owner setup-owner--ready" : "setup-owner"}>{item.ready ? "✓ Completo" : "A cargo del proyecto"}</span>
                )}
              </div>
            ))}
          </div>
        </Card>
      </section>
    );
  }

  return (
    <section className="overview-screen">
      <Card className="priority-card primary-actions-card">
        <div className="dashboard-panel__header">
          <div>
            <p className="kicker">Estado de la obra</p>
            <h2>Resumen operativo</h2>
          </div>
        </div>

        <div className="action-grid">
          <button
            className="action-tile"
            onClick={() => onStep("contractors")}
            type="button"
          >
            <span className="action-tile__copy">
              <strong>Contratistas</strong>
              <small>{detail.contractors.length} registrados</small>
            </span>
            <span aria-hidden="true">→</span>
          </button>

          <button
            className="action-tile"
            onClick={() => onStep("people")}
            type="button"
          >
            <span className="action-tile__copy">
              <strong>Personal</strong>
              <small>{detail.people.length} personas registradas</small>
            </span>
            <span aria-hidden="true">→</span>
          </button>

          <button
            className="action-tile"
            onClick={() => onStep("documents")}
            type="button"
          >
            <span className="action-tile__copy">
              <strong>Documentación</strong>
              <small>
                {pendingDocuments
                  ? `${pendingDocuments} requieren atención`
                  : "Sin pendientes"}
              </small>
            </span>
            <span aria-hidden="true">→</span>
          </button>

          <button
            className="action-tile"
            onClick={() => onStep("followup")}
            type="button"
          >
            <span className="action-tile__copy">
              <strong>Desvíos</strong>
              <small>
                {openFindings
                  ? `${openFindings} abiertos o por verificar`
                  : "Sin pendientes"}
              </small>
            </span>
            <span aria-hidden="true">→</span>
          </button>

          <button
            className="action-tile"
            onClick={() => onStep("machines")}
            type="button"
          >
            <span className="action-tile__copy">
              <strong>Maquinarias</strong>
              <small>
                {machineIssues
                  ? `${machineIssues} requieren atención`
                  : "Sin observaciones"}
              </small>
            </span>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </Card>

      {(pendingDocuments > 0 || openFindings > 0 || machineIssues > 0) && (
        <Card className="priority-card priority-card--attention">
          <div className="dashboard-panel__header">
            <div>
              <p className="kicker">Requiere intervención</p>
              <h2>Pendientes</h2>
            </div>
          </div>

          <ul className="priority-list">
            {pendingDocuments > 0 ? (
              <li>{pendingDocuments} documento(s) requieren revisión.</li>
            ) : null}

            {openFindings > 0 ? (
              <li>{openFindings} desvío(s) requieren seguimiento.</li>
            ) : null}

            {machineIssues > 0 ? (
              <li>{machineIssues} maquinaria(s) requieren atención.</li>
            ) : null}
          </ul>
        </Card>
      )}
    </section>
  );
}
type ResponsibilityCode =
  | "RESPONSABLE_HYS_PROYECTO"
  | "AUDITOR"
  | "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL"
  | "TECNICO_HYS_CONTRATISTA_PRINCIPAL";

const RESPONSIBILITIES: Array<{
  code: ResponsibilityCode;
  title: string;
  action: string;
  profession?: string;
}> = [
  {
    code: "RESPONSABLE_HYS_PROYECTO",
    title: "Responsable H&S del proyecto",
    action: "Cambiar responsable",
    profession: "LICENCIADO_HYS",
  },
  { code: "AUDITOR", title: "Auditor", action: "Cambiar auditor" },
  {
    code: "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
    title: "Responsable H&S de contratista principal",
    action: "Cambiar responsable",
    profession: "LICENCIADO_HYS",
  },
  {
    code: "TECNICO_HYS_CONTRATISTA_PRINCIPAL",
    title: "T├®cnico H&S de contratista principal",
    action: "Cambiar t├®cnico",
    profession: "TECNICO_HYS",
  },
];

function currentResponsibility(
  assignments: NonNullable<WorksiteDetail["functional_assignments"]>,
  code: ResponsibilityCode,
) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Argentina/Buenos_Aires",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? "";
  const today = `${part("year")}-${part("month")}-${part("day")}`;
  const current = assignments.filter(
    (assignment) =>
      assignment.function_code === code &&
      assignment.valid_from <= today &&
      (!assignment.valid_to || assignment.valid_to > today),
  );
  return [...current].sort((left, right) => {
    if (code === "AUDITOR") {
      const delegatedDifference =
        Number(Boolean(right.delegated_by_assignment_id)) -
        Number(Boolean(left.delegated_by_assignment_id));
      if (delegatedDifference) return delegatedDifference;
    }
    return (
      right.valid_from.localeCompare(left.valid_from) ||
      right.id.localeCompare(left.id)
    );
  })[0];
}

function ResponsablesStep({
  detail,
  busy,
  canManage,
  onAssign,
  onFinish,
}: {
  detail: WorksiteDetail;
  busy: string | null;
  canManage: boolean;
  onAssign: (
    event: FormEvent<HTMLFormElement>,
    code: ResponsibilityCode,
    currentId?: string,
  ) => void;
  onFinish: (assignmentId: string) => void;
}) {
  const [editingCode, setEditingCode] = useState<ResponsibilityCode | null>(
    null,
  );
  const [auditorProfession, setAuditorProfession] = useState("");
  const assignments = detail.functional_assignments ?? [];
  const principal = detail.contractors.find(
    (item) => item.participation_type === "PRINCIPAL",
  );
  const projectResponsible = currentResponsibility(
    assignments,
    "RESPONSABLE_HYS_PROYECTO",
  );
  const eligiblePeople = (code: ResponsibilityCode) =>
    detail.people.filter((person) => {
      if (code === "RESPONSABLE_HYS_PROYECTO") {
        return (
          person.profession_code === "LICENCIADO_HYS" &&
          person.contractor_id === null
        );
      }
      if (code === "AUDITOR") {
        return ["LICENCIADO_HYS", "TECNICO_HYS"].includes(
          person.profession_code ?? "",
        );
      }
      return (
        person.contractor_id === principal?.id &&
        person.profession_code ===
          RESPONSIBILITIES.find((item) => item.code === code)?.profession
      );
    });

  return (
    <section>
      <StepHeading
        eyebrow="02 · Responsables"
        title="Responsables de la obra"
        text="Asigná las responsabilidades operativas sin exponer el modelo técnico de actores, funciones y alcances."
      />
      <div className="responsibility-grid">
        {RESPONSIBILITIES.map((responsibility) => {
          const current = currentResponsibility(
            assignments,
            responsibility.code,
          );
          const people = eligiblePeople(responsibility.code);
          const isEditing = editingCode === responsibility.code;
          const delegatingAssignment =
            responsibility.code === "AUDITOR" ? projectResponsible : undefined;
          const isAuditor = responsibility.code === "AUDITOR";
          return (
            <Card className="responsibility-card" key={responsibility.code}>
              <div className="responsibility-card__heading">
                <div>
                  <p className="kicker">Responsabilidad</p>
                  <h3>{responsibility.title}</h3>
                </div>
                <StatusBadge value={current ? "VIGENTE" : "PENDIENTE"} />
              </div>
              {current ? (
                <div className="responsibility-card__person">
                  <strong>{current.person_name ?? "Persona asignada"}</strong>
                  <span>
                    {pilotLabel(current.profession_code)}
                    {current.represented_contractor_name
                      ? ` · ${current.represented_contractor_name}`
                      : ""}
                  </span>
                  <small>Desde {formatDate(current.valid_from)}</small>
                  {isAuditor && current.delegated_by_assignment_id ? (
                    <small>
                      Delegado por:{" "}
                      {assignments.find(
                        (item) =>
                          item.id === current.delegated_by_assignment_id,
                      )?.person_name ?? "Licenciado H&S del proyecto"}
                    </small>
                  ) : null}
                </div>
              ) : (
                <p className="empty-state">Pendiente de asignar</p>
              )}
              {canManage ? (
                <div className="responsibility-card__actions">
                  {!isEditing ? (
                    <button
                      className="button button--primary"
                      onClick={() => setEditingCode(responsibility.code)}
                      type="button"
                    >
                      {current ? responsibility.action : "Asignar"}
                    </button>
                  ) : null}
                  {current ? (
                    <button
                      className="button button--quiet"
                      disabled={busy !== null}
                      onClick={() => onFinish(current.id)}
                      type="button"
                    >
                      Finalizar
                    </button>
                  ) : null}
                </div>
              ) : null}
              {isEditing ? (
                <form
                  className="responsibility-form"
                  onSubmit={(event) =>
                    onAssign(event, responsibility.code, current?.id)
                  }
                >
                  <Field label={isAuditor ? "Persona auditora" : "Profesional"}>
                    <select
                      defaultValue=""
                      name="person_id"
                      onChange={(event) => {
                        if (isAuditor) {
                          setAuditorProfession(
                            people.find(
                              (person) => person.id === event.target.value,
                            )?.profession_code ?? "",
                          );
                        }
                      }}
                      required
                    >
                      <option disabled value="">
                        Seleccionar persona…
                      </option>
                      {people.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.display_name} ·{" "}
                          {pilotLabel(person.profession_code)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {isAuditor ? (
                    <Field
                      hint="Sólo es obligatorio cuando la persona auditora es Técnico H&S."
                      label="Delegado por"
                    >
                      <select
                        defaultValue=""
                        name="delegated_by_assignment_id"
                        required={auditorProfession === "TECNICO_HYS"}
                      >
                        <option value="">No requiere delegación</option>
                        {delegatingAssignment ? (
                          <option value={delegatingAssignment.id}>
                            {delegatingAssignment.person_name ??
                              "Licenciado H&S del proyecto"}
                          </option>
                        ) : null}
                      </select>
                    </Field>
                  ) : null}
                  <div className="responsibility-card__actions">
                    <button
                      className="button button--primary"
                      disabled={busy !== null || !people.length}
                    >
                      {current ? "Confirmar cambio" : "Asignar"}
                    </button>
                    <button
                      className="button button--quiet"
                      onClick={() => setEditingCode(null)}
                      type="button"
                    >
                      Cancelar
                    </button>
                  </div>
                  {!people.length ? (
                    <small className="permission-note">
                      No hay profesionales compatibles asignados a la obra.
                    </small>
                  ) : null}
                </form>
              ) : null}
            </Card>
          );
        })}
      </div>
      {!canManage ? (
        <PermissionCopy text="Sólo el Contratista principal y el Licenciado H&S del proyecto pueden administrar responsables. Esta vista es de solo lectura." />
      ) : null}
      <Card className="responsibility-history">
        <details>
          <summary>Historial de responsables</summary>
          {assignments.length ? (
            <ul className="responsibility-history__list">
              {assignments.map((assignment) => (
                <li key={assignment.id}>
                  <strong>
                    {assignment.person_name ?? "Persona asignada"}
                  </strong>
                  <span>
                    {FUNCTION_LABELS[assignment.function_code] ??
                      "Responsabilidad H&S"}
                  </span>
                  <small>
                    Desde {formatDate(assignment.valid_from)} · Hasta{" "}
                    {formatDate(assignment.valid_to)}
                  </small>
                  {assignment.assigned_by_label ? (
                    <small>Asignado por: {assignment.assigned_by_label}</small>
                  ) : null}
                  {assignment.delegated_by_assignment_id ? (
                    <small>
                      Delegado por:{" "}
                      {assignments.find(
                        (item) =>
                          item.id === assignment.delegated_by_assignment_id,
                      )?.person_name ?? "Licenciado H&S del proyecto"}
                    </small>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Todavía no hay responsables asignados.</EmptyState>
          )}
        </details>
      </Card>
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
  onStep?: (step: Step) => void;
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

type TechnicalFileComponent = {
  name: string;
  terms: readonly string[];
  keyLabel?: string;
};

type TechnicalFileSection = {
  title: string;
  components: readonly TechnicalFileComponent[];
};

const TECHNICAL_FILE_SECTIONS: readonly TechnicalFileSection[] = [
  {
    title: "Habilitaciones y ART",
    components: [
      { name: "Aviso de Obra", terms: ["aviso de obra"] },
      { name: "RAR", terms: ["rar"] },
      {
        name: "Entrega de credenciales",
        terms: ["entrega de credenciales", "credenciales"],
      },
      { name: "Visitas ART", terms: ["visitas art", "visita art"] },
    ],
  },
  {
    title: "Gestión H&S",
    components: [
      { name: "Programa de Seguridad", terms: ["programa de seguridad"] },
      { name: "Capacitaciones", terms: ["capacitaciones", "capacitación"] },
      {
        name: "Matrícula del Licenciado H&S responsable",
        terms: ["matrícula", "matricula", "licenciado h&s"],
      },
      {
        name: "Carga horaria semanal",
        terms: ["carga horaria", "horaria semanal"],
      },
    ],
  },
  {
    title: "Documentación técnica",
    components: [
      {
        name: "Memoria descriptiva de la obra",
        terms: ["memoria descriptiva"],
      },
      { name: "Plano de obrador", terms: ["plano de obrador", "obrador"] },
    ],
  },
  {
    title: "Controles y condiciones",
    components: [
      { name: "Puesta a tierra", terms: ["puesta a tierra"] },
      {
        name: "Registro de visitas del Licenciado H&S de la Contratista Principal",
        terms: ["registro de visitas", "visitas del licenciado"],
      },
    ],
  },
];

const AUXILIARY_SERVICES: readonly TechnicalFileComponent[] = [
  { name: "Baños", terms: ["baños", "banos"] },
  { name: "Vestuario", terms: ["vestuario"] },
  { name: "Comedor", terms: ["comedor"] },
  {
    name: "Tablero eléctrico",
    terms: ["tablero eléctrico", "tablero electrico"],
  },
  { name: "Extintores", terms: ["extintores", "extintor"] },
];

type ProjectFileComponent = TechnicalFileComponent & {
  action: "Completar" | "Adjuntar";
};

const PROJECT_FILE_COMPONENTS: readonly ProjectFileComponent[] = [
  {
    name: "Memoria descriptiva H&S",
    terms: ["memoria descriptiva"],
    action: "Completar",
  },
  {
    name: "Riesgos por etapa",
    terms: ["identificación de peligros", "evaluación de riesgos", "iper"],
    action: "Completar",
  },
  {
    name: "Medidas preventivas previstas",
    terms: ["medidas preventivas", "plan de emergencias", "emergencias"],
    action: "Completar",
  },
  {
    name: "Programa de Seguridad de Proyecto",
    terms: ["programa de seguridad"],
    action: "Completar",
  },
  {
    name: "Planos H&S de Proyecto",
    terms: [
      "plano de implantación",
      "plano de implantacion",
      "plano de obrador",
      "obrador",
    ],
    action: "Adjuntar",
  },
];

function documentForComponent(
  documents: WorksiteDetail["documents"],
  component: TechnicalFileComponent,
) {
  return documents.find((document) => {
    const searchable =
      `${document.title} ${document.document_type}`.toLowerCase();
    return component.terms.some((term) => searchable.includes(term));
  });
}

function TechnicalFileRow({
  component,
  document,
  canEdit,
}: {
  component: TechnicalFileComponent;
  document?: WorksiteDetail["documents"][number];
  canEdit: boolean;
}) {
  const keyData = document?.expires_on
    ? `Vence ${formatDate(document.expires_on)}`
    : document
      ? `Versión ${document.version}`
      : "Sin información cargada";

  return (
    <li className="technical-file-row">
      <div className="technical-file-row__name">
        <strong>{component.name}</strong>
      </div>
      <StatusBadge value={document?.status ?? "PENDIENTE"} />
      <span className="technical-file-row__key">{keyData}</span>
      {canEdit ? (
        <button
          className="button button--quiet technical-file-row__action"
          type="button"
        >
          {document ? "Actualizar" : "Cargar"}
        </button>
      ) : null}
    </li>
  );
}

function ProjectFileComponentCard({
  component,
  document,
  canEdit,
}: {
  component: ProjectFileComponent;
  document?: WorksiteDetail["documents"][number];
  canEdit: boolean;
}) {
  return (
    <Card className="technical-file-section">
      <div className="technical-file-section__heading">
        <h3>{component.name}</h3>
        {canEdit ? (
          <button className="button button--quiet" type="button">
            {component.action}
          </button>
        ) : null}
      </div>
      {document ? <small>Documento cargado: {document.title}</small> : null}
      {component.name === "Programa de Seguridad de Proyecto" ? (
        canEdit ? (
          <div className="form-grid">
            <label>
              Auditor asignado
              <input defaultValue="Sin asignar" />
            </label>
            <label>
              Profesión del auditor
              <input defaultValue="Sin especificar" />
            </label>
            <label>
              Carga horaria semanal del auditor
              <input defaultValue="Sin especificar" />
            </label>
          </div>
        ) : (
          <dl className="form-grid">
            <div>
              <dt>Auditor asignado</dt>
              <dd>Sin asignar</dd>
            </div>
            <div>
              <dt>Profesión del auditor</dt>
              <dd>Sin especificar</dd>
            </div>
            <div>
              <dt>Carga horaria semanal del auditor</dt>
              <dd>Sin especificar</dd>
            </div>
          </dl>
        )
      ) : null}
    </Card>
  );
}

function AuxiliaryServiceRow({
  component,
  available,
  canEdit,
  onChange,
}: {
  component: TechnicalFileComponent;
  available: boolean | null;
  canEdit: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <li className="technical-file-row technical-file-row--auxiliary">
      <div className="technical-file-row__name">
        <strong>{component.name}</strong>
      </div>
      {canEdit ? (
        <div
          aria-label={`${component.name}: presencia o disponibilidad`}
          className="availability-control"
          role="group"
        >
          {[true, false].map((value) => {
            const label = value ? "Sí" : "No";
            return (
              <label key={label}>
                <input
                  checked={available === value}
                  name={`auxiliary-${component.name}`}
                  onChange={() => onChange(value)}
                  type="radio"
                />
                <span>{label}</span>
              </label>
            );
          })}
        </div>
      ) : (
        <span className="availability-value">
          {available === null ? "Sin seleccionar" : available ? "Sí" : "No"}
        </span>
      )}
    </li>
  );
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
  actor,
}: {
  detail: WorksiteDetail;
  actor: PilotActor;
}) {
  const [view, setView] = useState<"index" | "technical-file" | "project-file">(
    "index",
  );
  const principalContractor = detail.contractors.find(
    (item) => item.participation_type === "PRINCIPAL",
  );
  const technicalDocuments = detail.documents.filter(
    (item) =>
      item.subject_kind === "CONTRACTOR" &&
      item.subject_id === principalContractor?.id,
  );
  const projectDocuments = detail.documents.filter(
    (item) => item.subject_kind === "WORKSITE" && item.subject_id === detail.id,
  );
  const canEditPrincipalFile = PRINCIPAL_TECHNICAL_FILE_EDITORS.includes(actor);
  const canEditProjectFile = PROJECT_TECHNICAL_FILE_EDITORS.includes(actor);
  const [availability, setAvailability] = useState<
    Record<string, boolean | null>
  >(() =>
    Object.fromEntries(AUXILIARY_SERVICES.map((item) => [item.name, null])),
  );
  const documentCounts = technicalDocuments.reduce<Record<string, number>>(
    (counts, item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
      return counts;
    },
    {},
  );
  const attentionCount =
    (documentCounts.VENCIDO ?? 0) +
    (documentCounts.RECHAZADO ?? 0) +
    (documentCounts.OBSERVADO ?? 0);
  const expiringCount = documentCounts.POR_VENCER ?? 0;
  const fileStatus = attentionCount
    ? "Requiere atención"
    : expiringCount
      ? "Por vencer"
      : technicalDocuments.length
        ? "Documentación vigente"
        : "Sin documentación";
  const fileStatusTone = attentionCount
    ? "VENCIDO"
    : expiringCount
      ? "POR_VENCER"
      : technicalDocuments.length
        ? "VIGENTE"
        : "PENDIENTE";

  if (view === "index") {
    return (
      <section>
        <StepHeading
          eyebrow="05 · Legajos Técnicos"
          title="Legajos Técnicos"
          text="Accedé a los dos legajos técnicos que organizan la documentación de la obra."
        />
        <div className="documentation-index">
          <Card className="documentation-entry documentation-entry--primary">
            <div className="documentation-entry__number">01</div>
            <div>
              <p className="kicker">Empresa principal</p>
              <h3>Legajo Técnico - Contratista Principal</h3>
              <div className="technical-file-status">
                <StatusBadge value={fileStatusTone} />
                <strong>{fileStatus}</strong>
              </div>
              <p>
                Documentación propia de la empresa principal, con su estado de
                vigencia y seguimiento.
              </p>
              {principalContractor ? (
                <small>Asociado a {principalContractor.legal_name}</small>
              ) : null}
            </div>
            <button
              className="button button--primary"
              onClick={() => setView("technical-file")}
              type="button"
            >
              Ver legajo
            </button>
          </Card>

          <Card className="documentation-entry documentation-entry--project">
            <div className="documentation-entry__number">02</div>
            <div>
              <p className="kicker">Alcance de la obra</p>
              <h3>Legajo Técnico - Proyecto</h3>
              <p>
                Documentación que debe reunirse y revisar antes del inicio de la
                obra.
              </p>
            </div>
            <button
              className="button button--dark"
              onClick={() => setView("project-file")}
              type="button"
            >
              Ver legajo
            </button>
          </Card>
        </div>
      </section>
    );
  }

  if (view === "project-file") {
    return (
      <section>
        <div className="documentation-detail-heading">
          <button
            className="button button--quiet"
            onClick={() => setView("index")}
            type="button"
          >
            ← Volver a legajos técnicos
          </button>
          <StepHeading
            eyebrow="02 · Legajo Técnico - Proyecto"
            title="Legajo Técnico - Proyecto"
            text="Completá y revisá la documentación necesaria para habilitar el inicio de la obra."
          />
          {!canEditProjectFile ? (
            <PermissionCopy text="Modo consulta: este perfil puede revisar el legajo del proyecto, pero no editarlo." />
          ) : null}
        </div>
        <div className="technical-file-sections">
          {PROJECT_FILE_COMPONENTS.map((component) => (
            <ProjectFileComponentCard
              key={component.name}
              component={component}
              document={documentForComponent(projectDocuments, component)}
              canEdit={canEditProjectFile}
            />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="documentation-detail-heading">
        <button
          className="button button--quiet"
          onClick={() => setView("index")}
          type="button"
        >
          ← Volver a legajos técnicos
        </button>
        <StepHeading
          eyebrow="01 · Legajo Técnico - Contratista Principal"
          title="Legajo Técnico - Contratista Principal"
          text="Estructura de documentación, habilitaciones y condiciones de la Contratista Principal."
        />
        {!canEditPrincipalFile ? (
          <PermissionCopy text="Modo consulta: este perfil puede revisar el legajo de la Contratista Principal, pero no editarlo." />
        ) : null}
      </div>
      <div className="technical-file-sections">
        {TECHNICAL_FILE_SECTIONS.map((section) => (
          <Card key={section.title} className="technical-file-section">
            <div className="technical-file-section__heading">
              <h3>{section.title}</h3>
              <span>{section.components.length} componentes</span>
            </div>
            <ul className="technical-file-list">
              {section.components.map((component) => (
                <TechnicalFileRow
                  key={component.name}
                  component={component}
                  document={documentForComponent(technicalDocuments, component)}
                  canEdit={
                    canEditPrincipalFile &&
                    (!PRINCIPAL_TECHNICAL_FILE_LICENSED_ONLY.has(
                      component.name,
                    ) ||
                      actor === "licenciado-contratista-principal")
                  }
                />
              ))}
              {section.title === "Controles y condiciones" ? (
                <li className="technical-file-subsection">
                  <div className="technical-file-subsection__heading">
                    <strong>Servicios auxiliares del obrador</strong>
                    <span>Presencia o disponibilidad</span>
                  </div>
                  <ul className="technical-file-list technical-file-list--nested">
                    {AUXILIARY_SERVICES.map((component) => (
                      <AuxiliaryServiceRow
                        key={component.name}
                        component={component}
                        available={availability[component.name] ?? null}
                        canEdit={canEditPrincipalFile}
                        onChange={(value) =>
                          setAvailability((current) => ({
                            ...current,
                            [component.name]: value,
                          }))
                        }
                      />
                    ))}
                  </ul>
                </li>
              ) : null}
            </ul>
          </Card>
        ))}
      </div>
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
    <section className="audit-screen">
      <StepHeading
        eyebrow="07 · Campo"
        title="Auditoría"
        text="El checklist es sintético y online. Un resultado no conforme crea el desvío de forma atómica."
      />
      {!audit || audit.status === "FINALIZADA" ? (
        <Card className="action-card audit-start-card">
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
        <Card className="audit-history-card">
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
        <Card className="audit-active-card">
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
            {finding.status === "PENDIENTE_VERIFICACION" && canVerify ? (
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
                  disabled={busy !== null}
                >
                  Registrar verificación
                </button>
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
