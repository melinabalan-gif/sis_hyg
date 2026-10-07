"use client";

import { type FormEvent, useState } from "react";
import type {
  DocumentCreate,
  DocumentReviewCreate,
  PilotDocument,
} from "../lib/pilot-api";

export interface TechnicalMetadata {
  [key: string]: unknown;
  schema?: "hys.technical_metadata.v1";
  detail?: string;
  available?: boolean;
  weekly_hours?: number;
  auditor_assignment_id?: string | null;
}

export function documentMetadata(document?: PilotDocument): TechnicalMetadata {
  if (!document?.notes) return {};
  try {
    const value: unknown = JSON.parse(document.notes);
    if (!value || typeof value !== "object" || Array.isArray(value))
      return { detail: document.notes };
    const metadata = value as Record<string, unknown>;
    if (metadata.schema !== "hys.technical_metadata.v1")
      return { detail: document.notes };
    return {
      ...metadata,
      detail: typeof metadata.detail === "string" ? metadata.detail : "",
      available:
        typeof metadata.available === "boolean"
          ? metadata.available
          : undefined,
      weekly_hours:
        typeof metadata.weekly_hours === "number" &&
        Number.isFinite(metadata.weekly_hours) &&
        metadata.weekly_hours >= 1 &&
        metadata.weekly_hours <= 168 &&
        Number.isInteger(metadata.weekly_hours * 2)
          ? metadata.weekly_hours
          : undefined,
      auditor_assignment_id:
        typeof metadata.auditor_assignment_id === "string"
          ? metadata.auditor_assignment_id
          : null,
      schema: "hys.technical_metadata.v1",
    };
  } catch {
    return { detail: document.notes };
  }
}

export function DocumentMetadataEditor({
  title,
  document,
  subjectKind,
  subjectId,
  programAssignmentId,
  onSave,
  onCancel,
}: {
  title: string;
  document?: PilotDocument;
  subjectKind: "WORKSITE" | "CONTRACTOR";
  subjectId: string;
  programAssignmentId?: string | null;
  onSave: (body: DocumentCreate, documentId?: string) => Promise<boolean>;
  onCancel: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const metadata = documentMetadata(document);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const detail = String(form.get("notes") ?? "").trim();
    const notes =
      programAssignmentId !== undefined
        ? JSON.stringify({
            ...metadata,
            schema: "hys.technical_metadata.v1",
            detail,
            weekly_hours: Number(form.get("weekly_hours")),
            auditor_assignment_id: programAssignmentId,
          })
        : metadata.schema
          ? JSON.stringify({ ...metadata, detail })
          : detail;
    setSaving(true);
    try {
      if (
        await onSave(
          {
            title,
            document_type: document?.document_type ?? "LEGAJO_TECNICO",
            subject_kind: subjectKind,
            subject_id: subjectId,
            notes,
            valid_from: String(form.get("valid_from") ?? "") || null,
            expires_on: String(form.get("expires_on") ?? "") || null,
          },
          document?.id,
        )
      )
        onCancel();
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="card" role="region" aria-label={`Editar ${title}`}>
      <h3>
        {document ? "Nueva versión" : "Carga de metadatos"}: {title}
      </h3>
      <p>
        Se conserva el historial. Sólo referencias sintéticas; este piloto no
        admite archivos binarios.
      </p>
      <form className="form-grid" onSubmit={(event) => void submit(event)}>
        <label className="field">
          Detalle del documento
          <textarea
            name="notes"
            required
            maxLength={4000}
            defaultValue={metadata.detail ?? document?.notes ?? ""}
          />
        </label>
        <label className="field">
          Vigente desde
          <input
            name="valid_from"
            type="date"
            defaultValue={document?.valid_from ?? ""}
          />
        </label>
        <label className="field">
          Vencimiento
          <input
            name="expires_on"
            type="date"
            defaultValue={document?.expires_on ?? ""}
          />
        </label>
        {programAssignmentId !== undefined ? (
          <label className="field">
            Carga horaria semanal del auditor
            <input
              name="weekly_hours"
              type="number"
              min={1}
              max={168}
              step={0.5}
              required
              defaultValue={metadata.weekly_hours}
            />
          </label>
        ) : null}
        <button className="button button--primary" disabled={saving}>
          Guardar metadatos
        </button>
        <button
          className="button button--quiet"
          type="button"
          disabled={saving}
          onClick={onCancel}
        >
          Cancelar carga
        </button>
      </form>
    </section>
  );
}

export function DocumentReviewForm({
  document,
  onReview,
}: {
  document: PilotDocument;
  onReview: (
    documentId: string,
    body: DocumentReviewCreate,
  ) => Promise<boolean>;
}) {
  const [saving, setSaving] = useState(false);
  const current = document.versions.find(
    (version) => version.version_number === document.version,
  );
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current) return;
    const form = new FormData(event.currentTarget);
    setSaving(true);
    try {
      await onReview(document.id, {
        document_version_id: current.id,
        result: String(form.get("result")) as DocumentReviewCreate["result"],
        foundation: String(form.get("foundation")).trim(),
      });
    } finally {
      setSaving(false);
    }
  }
  return (
    <details>
      <summary>
        Revisar {document.title} · versión {document.version}
      </summary>
      <form className="form-grid" onSubmit={(event) => void submit(event)}>
        <label className="field">
          Resultado de revisión
          <select name="result" defaultValue="OBSERVADO">
            <option>OBSERVADO</option>
            <option>APROBADO</option>
            <option>RECHAZADO</option>
          </select>
        </label>
        <label className="field">
          Fundamento de revisión
          <textarea name="foundation" required maxLength={4000} />
        </label>
        <button
          className="button button--primary"
          disabled={saving || !current}
        >
          Registrar revisión independiente
        </button>
      </form>
    </details>
  );
}
