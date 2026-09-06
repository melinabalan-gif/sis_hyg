export const PILOT_ACTORS = [
  {
    value: "tecnico",
    label: "Técnico H&S de contratista principal",
    role: "TECNICO",
    id: "00000000-0000-4000-8000-000000000002",
  },
  {
    value: "auditor",
    label: "Auditor",
    role: "AUDITOR",
    id: "00000000-0000-4000-8000-000000000001",
  },
  {
    value: "responsable",
    label: "Licenciado H&S del proyecto",
    role: "RESPONSABLE_HYS",
    id: "00000000-0000-4000-8000-000000000003",
  },
  {
    value: "licenciado-contratista-principal",
    label: "Licenciado H&S de contratista principal",
    role: "RESPONSABLE_HYS",
    id: "00000000-0000-4000-8000-000000000004",
  },
  {
    value: "contratista-principal",
    label: "Contratista principal",
    role: "CONTRATISTA",
    id: "00000000-0000-4000-8000-000000000005",
  },
] as const;

export type PilotActor = (typeof PILOT_ACTORS)[number]["value"];
export type PilotRole = (typeof PILOT_ACTORS)[number]["role"];

export type Identifier = string;

export interface WorksiteSummary {
  id: Identifier;
  code: string;
  name: string;
  jurisdiction: string;
  country?: string | null;
  province?: string | null;
  municipality?: string | null;
  status: string;
  version?: number;
}

export interface WorksiteStage {
  id: Identifier;
  worksite_id: Identifier;
  code: string;
  name: string;
  started_on: string;
  ended_on?: string | null;
  sector?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  status?: "PLANIFICADA" | "ACTIVA" | "CERRADA";
  history?: WorksiteStageEvent[];
}

export interface WorksiteStageEvent {
  id: Identifier;
  event_type: string;
  actor_id: Identifier;
  detail: string;
  created_at: string;
}

export interface Contractor {
  id: Identifier;
  legal_name: string;
  trade: string;
  started_on?: string;
  ended_on?: string | null;
  participation_type?: string;
  parent_contracting_company_id?: Identifier | null;
  parent_contracting_company_name?: string | null;
}

export interface Person {
  id: Identifier;
  display_name: string;
  role_label: string;
  profession_code?: string;
  contractor_id?: Identifier | null;
  contractor_name?: string;
  started_on?: string;
  ended_on?: string | null;
  habilitation_status?: string;
  habilitation_verified_by?: Identifier | null;
  habilitation_verified_at?: string | null;
  habilitation_observation?: string | null;
}

export type DocumentSubjectKind =
  "WORKSITE" | "CONTRACTOR" | "PERSON" | "MACHINE";

export interface PilotDocumentVersion {
  id: Identifier;
  version_number: number;
  title: string;
  document_type: string;
  review_status: string;
  valid_from?: string | null;
  expires_on?: string | null;
  notes?: string | null;
  actor_id: Identifier;
  created_at: string;
}

export interface PilotDocument {
  id: Identifier;
  version: number;
  title: string;
  document_type: string;
  review_status: string;
  status: string;
  valid_from?: string | null;
  expires_on?: string | null;
  notes?: string | null;
  subject_kind: DocumentSubjectKind;
  subject_id: Identifier;
  subject_name?: string;
  versions: PilotDocumentVersion[];
  uploaded_by?: Identifier | null;
  uploaded_at?: string | null;
  reviews?: DocumentReview[];
}

export interface DocumentReview {
  id: Identifier;
  reviewer: Identifier;
  reviewer_function: string;
  reviewed_at: string;
  result: "APROBADO" | "OBSERVADO" | "RECHAZADO";
  foundation: string;
}

export interface Machine {
  id: Identifier;
  assignment_id: Identifier;
  internal_code: string;
  description: string;
  status: string;
  version: number;
  contractor_id?: Identifier | null;
  contractor_name?: string | null;
  inspection_reason?: string | null;
  inspected_at?: string | null;
  started_on: string;
  ended_on?: string | null;
  inspections: MachineInspection[];
  machine_type?: string | null;
  brand?: string | null;
  model?: string | null;
  license_plate?: string | null;
  operator_person_id?: Identifier | null;
}

export interface MachineInspection {
  id: Identifier;
  resulting_status: string;
  reason: string;
  actor_id: Identifier;
  inspected_at: string;
  checklist?: Record<string, string>;
  evidence_note?: string | null;
  inspector_function?: string | null;
  validations?: MachineInspectionValidation[];
}

export interface MachineInspectionValidation {
  id: Identifier;
  validated_by: Identifier;
  validator_function: string;
  notes: string;
  validated_at: string;
}

export interface AuditControl {
  id: Identifier;
  catalog_code: string;
  catalog_title: string;
  result: string;
  reason?: string | null;
  finding_id?: Identifier | null;
}

export interface AuditCatalogControl {
  catalog_code: string;
  catalog_title: string;
}

export interface Audit {
  id: Identifier;
  status: string;
  started_at: string;
  finalized_at?: string | null;
  worksite_id?: Identifier | null;
  auditor_actor_id?: Identifier | null;
  auditor_assignment_id?: Identifier | null;
  associated_professional_person_id?: Identifier | null;
  audit_date?: string | null;
  author_actor?: string;
  editor_actor?: string;
  available_controls: AuditCatalogControl[];
  controls: AuditControl[];
  auditor_name?: string | null;
  auditor_function?: string | null;
  responsible_professional_name?: string | null;
}

export interface FunctionalAssignment {
  id: Identifier;
  worksite_id: Identifier;
  actor_id: Identifier;
  assigned_by_actor_id?: Identifier | null;
  assigned_by_label?: string | null;
  actor_key: string;
  actor_label: string;
  person_id?: Identifier | null;
  person_name?: string | null;
  profession_code?: string | null;
  function_code: string;
  represented_contractor_id?: Identifier | null;
  represented_contractor_name?: string | null;
  delegated_by_assignment_id?: Identifier | null;
  permission_scope: string;
  valid_from: string;
  valid_to?: string | null;
  version: number;
}

export interface FindingCorrection {
  id: Identifier;
  description: string;
  evidence_note: string;
  created_by?: string;
  created_at: string;
}

export interface FindingVerification {
  id: Identifier;
  decision: string;
  notes: string;
  verified_by?: string;
  created_at: string;
}

export interface FindingEvent {
  id: Identifier;
  event_type: string;
  from_status?: string | null;
  to_status: string;
  actor_id?: string;
  detail?: string | null;
  created_at: string;
}

export interface Finding {
  id: Identifier;
  audit_id: Identifier;
  audit_control_id?: Identifier | null;
  title: string;
  description: string;
  status: string;
  severity_code: string;
  severity_label?: string;
  due_at: string;
  overdue?: boolean;
  created_by?: string;
  created_at?: string;
  closed_at?: string | null;
  affected_contractor_id?: Identifier | null;
  affected_contractor_name?: string | null;
  responsible_contractor_id?: Identifier | null;
  responsible_contractor_name?: string | null;
  responsible_person_id?: Identifier | null;
  responsible_person_name?: string | null;
  source_label?: string | null;
  corrections: FindingCorrection[];
  verifications: FindingVerification[];
  events: FindingEvent[];
}

export interface WorksiteMetrics {
  documents: {
    total: number;
    by_status: Record<string, number>;
  };
  findings: {
    total: number;
    by_status: Record<string, number>;
    overdue: number;
  };
  machines: {
    total: number;
    by_status: Record<string, number>;
  };
  latest_audit: {
    id: Identifier;
    status: string;
    started_at: string;
    finalized_at?: string | null;
  } | null;
  controls: {
    audit_id: Identifier | null;
    numerator: number;
    denominator: number;
    ratio: number | null;
    excluded: {
      no_aplica: number;
      no_verificado: number;
    };
  };
  calculated_at: string;
}

export interface WorksiteDetail extends WorksiteSummary {
  stages: WorksiteStage[];
  contractors: Contractor[];
  functional_assignments?: FunctionalAssignment[];
  people: Person[];
  documents: PilotDocument[];
  machines: Machine[];
  audits: Audit[];
  findings: Finding[];
  metrics: WorksiteMetrics;
}

export class PilotApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "PilotApiError";
    this.status = status;
  }
}

function errorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const value = payload as Record<string, unknown>;
    const errors = Array.isArray(value.errors)
      ? value.errors
          .map((item) => {
            if (item && typeof item === "object" && "message" in item) {
              return String((item as { message: unknown }).message);
            }
            return String(item);
          })
          .join(". ")
      : "";
    if (errors && typeof value.detail === "string") {
      return `${value.detail} ${errors}`;
    }
    if (errors) return errors;
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.title === "string") return value.title;
    if (typeof value.message === "string") return value.message;
    if (Array.isArray(value.detail)) {
      return value.detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return String(item);
        })
        .join(". ");
    }
  }
  return `La operación no pudo completarse (HTTP ${status}).`;
}

async function request<T>(
  path: string,
  actor: PilotActor,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Pilot-Actor": actor,
      ...init?.headers,
    },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new PilotApiError(
      response.status,
      errorMessage(payload, response.status),
    );
  }
  return payload as T;
}

export function listWorksites(actor: PilotActor): Promise<WorksiteSummary[]> {
  return request<WorksiteSummary[]>("/worksites", actor);
}

export function getWorksite(
  id: Identifier,
  actor: PilotActor,
): Promise<WorksiteDetail> {
  return request<WorksiteDetail>(`/worksites/${id}`, actor);
}

export function postPilot<T>(
  path: string,
  actor: PilotActor,
  body: Record<string, unknown> = {},
): Promise<T> {
  return request<T>(path, actor, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function downloadWorksiteReport(
  id: Identifier,
  actor: PilotActor,
): Promise<Blob> {
  const response = await fetch(`/api/v1/worksites/${id}/report.pdf`, {
    headers: {
      Accept: "application/pdf",
      "X-Pilot-Actor": actor,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new PilotApiError(
      response.status,
      errorMessage(payload, response.status),
    );
  }
  return response.blob();
}

export async function downloadAuditReport(
  id: Identifier,
  actor: PilotActor,
): Promise<Blob> {
  const response = await fetch(`/api/v1/audits/${id}/report.pdf`, {
    headers: {
      Accept: "application/pdf",
      "X-Pilot-Actor": actor,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new PilotApiError(
      response.status,
      errorMessage(payload, response.status),
    );
  }
  return response.blob();
}

export function actorRole(actor: PilotActor): PilotRole {
  return PILOT_ACTORS.find((item) => item.value === actor)?.role ?? "TECNICO";
}

const PILOT_LABELS: Record<string, string> = {
  ACTIVE: "Activa",
  ABIERTO: "Abierto",
  ARCHIVED: "Archivada",
  ACTIVA: "Activa",
  ACTIVO: "Activo",
  APROBADO: "Aprobado",
  AUDITOR: "Auditor",
  CERRADA: "Cerrada",
  CERRADO: "Cerrado",
  CON_OBSERVACIONES: "Con observaciones",
  CONTRATISTA: "Contratista",
  CUMPLE: "Cumple",
  CREATED_FROM_CONTROL: "Desvío detectado durante auditoría",
  CORRECTION_ADDED: "Corrección informada",
  DOCUMENTACION_INCOMPLETA: "Documentación incompleta",
  EN_CURSO: "En curso",
  EN_CORRECCION: "En corrección",
  FINALIZADA: "Finalizada",
  FUERA_DE_SERVICIO: "Fuera de servicio",
  HABILITADO: "Habilitado",
  ALTA: "Alta",
  BAJA: "Baja",
  CRITICA: "Crítica",
  LICENCIADO_HYS: "Licenciado H&S",
  NO_APLICA: "No aplica",
  NO_CUMPLE: "No cumple",
  NO_HABILITADO: "No habilitado",
  NO_VERIFICADO: "No verificado",
  OBSERVADO: "Observado",
  OPERATIVA: "Operativa",
  PENDIENTE: "Pendiente",
  PENDIENTE_VERIFICACION: "Pendiente de verificación",
  PLANIFICADA: "Planificada",
  PRINCIPAL: "Contratista principal",
  RECHAZADO: "Rechazado",
  RECHAZADA: "Rechazada",
  RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL:
    "Licenciado H&S de contratista principal",
  RESPONSABLE_HYS_PROYECTO: "Licenciado H&S del proyecto",
  RESPONSABLE_HYS_CONTRATISTA: "Licenciado H&S de contratista",
  SUBMITTED_FOR_VERIFICATION: "Corrección enviada a verificación",
  TECNICO_HYS: "Técnico H&S",
  TECNICO_HYS_CONTRATISTA_PRINCIPAL: "Técnico H&S de contratista principal",
  TECNICO_HYS_CONTRATISTA: "Técnico H&S de contratista",
  UNREGISTERED_PERSON_FOUND: "Persona no registrada detectada",
  VERIFICATION_ACEPTADA: "Corrección verificada y desvío cerrado",
  VERIFICATION_RECHAZADA: "Corrección rechazada",
  VENCIDO: "Vencido",
  VIGENTE: "Vigente",
};

export function pilotLabel(value?: string | null): string {
  if (!value) return "Sin informar";
  return PILOT_LABELS[value] ?? value.replaceAll("_", " ").toLowerCase();
}

export function formatDate(value?: string | null): string {
  if (!value) return "Sin fecha";
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T12:00:00Z`
    : value;
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(normalized));
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(value));
}
