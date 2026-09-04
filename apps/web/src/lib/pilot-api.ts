export const PILOT_ACTORS = [
  { value: "tecnico", label: "Técnico de obra", role: "TECNICO" },
  { value: "auditor", label: "Auditor", role: "AUDITOR" },
  {
    value: "responsable",
    label: "Responsable H&S",
    role: "RESPONSABLE_HYS",
  },
  {
    value: "responsable-suplente",
    label: "Responsable H&S suplente",
    role: "RESPONSABLE_HYS",
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
}

export interface Contractor {
  id: Identifier;
  legal_name: string;
  trade: string;
  started_on?: string;
  ended_on?: string | null;
}

export interface Person {
  id: Identifier;
  display_name: string;
  role_label: string;
  contractor_id: Identifier;
  contractor_name?: string;
  started_on?: string;
  ended_on?: string | null;
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
  inspection_reason: string;
  inspected_at: string;
  started_on: string;
  ended_on?: string | null;
  inspections: MachineInspection[];
}

export interface MachineInspection {
  id: Identifier;
  resulting_status: string;
  reason: string;
  actor_id: Identifier;
  inspected_at: string;
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
  author_actor?: string;
  editor_actor?: string;
  available_controls: AuditCatalogControl[];
  controls: AuditControl[];
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
  title: string;
  description: string;
  status: string;
  severity_code: string;
  severity_label?: string;
  due_at: string;
  overdue?: boolean;
  created_by?: string;
  closed_at?: string | null;
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

export function actorRole(actor: PilotActor): PilotRole {
  return PILOT_ACTORS.find((item) => item.value === actor)?.role ?? "TECNICO";
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
