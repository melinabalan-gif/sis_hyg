"""Deterministic PDF reports built only from persisted synthetic records."""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from hys_api.modules.pilot.schemas import WorksiteDetail


def _text(value: object) -> str:
    if isinstance(value, StrEnum):
        value = value.value
    normalized = unicodedata.normalize("NFKD", str(value))
    return normalized.encode("ascii", "ignore").decode("ascii")


_LABELS = {
    "ABIERTO": "Abierto",
    "ALTA": "Alta",
    "APROBADO": "Aprobado",
    "AUDITOR_DELEGADO_PROYECTO": "Tecnico auditor delegado del proyecto",
    "CERRADO": "Cerrado",
    "CON_OBSERVACIONES": "Con observaciones",
    "CUMPLE": "Cumple",
    "CRITICA": "Critica",
    "EN_CORRECCION": "En correccion",
    "FINALIZADA": "Finalizada",
    "FUERA_DE_SERVICIO": "Fuera de servicio",
    "BAJA": "Baja",
    "MEDIA": "Media",
    "NO_APLICA": "No aplica",
    "NO_CUMPLE": "No cumple",
    "NO_VERIFICADO": "No verificado",
    "OBSERVADO": "Observado",
    "OPERATIVA": "Operativa",
    "PENDIENTE": "Pendiente",
    "PENDIENTE_VERIFICACION": "Pendiente de verificacion",
    "RECHAZADO": "Rechazado",
    "RECHAZADA": "Rechazada",
    "RESPONSABLE_HYS_CONTRATISTA": "Licenciado H&S de contratista",
    "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL": "Licenciado H&S de contratista principal",
    "RESPONSABLE_HYS_PROYECTO": "Licenciado H&S del proyecto",
    "TECNICO_HYS_CONTRATISTA": "Tecnico H&S de contratista",
    "TECNICO_HYS_CONTRATISTA_PRINCIPAL": "Tecnico H&S de contratista principal",
    "VENCIDO": "Vencido",
    "VIGENTE": "Vigente",
}


def _label(value: object) -> str:
    if value is None:
        return "Sin informar"
    raw = value.value if isinstance(value, StrEnum) else str(value)
    return _LABELS.get(raw, raw.replace("_", " ").capitalize())


def _responsibility_lines(detail: WorksiteDetail) -> list[str]:
    lines = ["Responsables y alcance"]
    assignments = sorted(
        detail.functional_assignments,
        key=lambda item: (item.function_code, item.person_name or "", str(item.id)),
    )
    if not assignments:
        return [*lines, "Sin asignaciones profesionales explicitas."]
    lines.extend(
        f"- {_text(item.person_name or item.actor_label)} | {_label(item.function_code)} | "
        f"Representa: {_text(item.represented_contractor_name or 'Proyecto / obra')} | "
        f"Alcance: {_label(item.permission_scope)}"
        for item in assignments
    )
    return lines


def _document_lines(detail: WorksiteDetail) -> list[str]:
    lines = ["Documentacion y revision"]
    for item in sorted(detail.documents, key=lambda value: (value.title, str(value.id))):
        lines.append(
            f"- {_text(item.title)} | {_label(item.status)} | "
            f"Revision: {_label(item.review_status)} | "
            f"Vence: {_text(item.expires_on or 'Sin fecha')}"
        )
        for review in item.reviews:
            lines.append(
                f"  Revision {_label(review.result)} | {_text(review.foundation)} | "
                f"{_text(review.reviewer_function)} | {_text(review.reviewed_at)}"
            )
    return lines


def _machine_lines(detail: WorksiteDetail) -> list[str]:
    lines = ["Maquinarias e inspecciones"]
    for machine in sorted(detail.machines, key=lambda value: (value.internal_code, str(value.id))):
        lines.append(
            f"- {_text(machine.internal_code)} | {_text(machine.description)} | "
            f"Estado: {_label(machine.status)} | "
            f"Operador: {_text(machine.operator_person_id or 'Sin asignar')}"
        )
        for inspection in machine.inspections:
            checklist = "; ".join(
                f"{_text(key)}={_label(value)}"
                for key, value in sorted(inspection.checklist.items())
            )
            lines.append(
                f"  Inspeccion {_label(inspection.resulting_status)} | "
                f"{_text(inspection.reason)} | "
                f"Inspector: {_text(inspection.inspector_function or inspection.actor_id)} | "
                f"{_text(inspection.inspected_at)}"
            )
            lines.append(f"  Checklist: {checklist or 'Sin informar'}")
            for validation in inspection.validations:
                lines.append(
                    f"  Validacion: {_text(validation.validator_function)} | "
                    f"{_text(validation.notes)} | {_text(validation.validated_at)}"
                )
    return lines


def _report_lines(detail: WorksiteDetail) -> list[str]:
    metrics = detail.metrics
    lines = [
        "H&S Gestion - Reporte Ejecutivo de Obra",
        f"Obra: {detail.code} - {detail.name}",
        f"Jurisdiccion: {detail.jurisdiction} | Estado: {_label(detail.status)}",
        "Organizacion: Piloto H&S - datos sinteticos",
        f"Generado: {metrics.calculated_at.isoformat()}",
        "",
        *_responsibility_lines(detail),
        "",
        *_document_lines(detail),
        "",
        f"Contratistas: {len(detail.contractors)}",
    ]
    lines.extend(
        f"- {_text(contractor.legal_name)} | "
        f"{_label(contractor.participation_type or 'CONTRACTOR')}"
        for contractor in detail.contractors
    )
    lines.extend(["", f"Personal registrado: {len(detail.people)}"])
    lines.extend(
        f"- {_text(person.display_name)} | Habilitacion: {_label(person.habilitation_status)}"
        for person in detail.people
    )
    lines.extend(
        [
            "",
            *_machine_lines(detail),
            "",
            "Auditorias",
            f"Registradas: {len(detail.audits)}",
            f"Controles que cumplen: {metrics.controls.numerator}",
            f"Controles evaluados: {metrics.controls.denominator}",
            f"No aplicables: {metrics.controls.excluded.no_aplica}",
            f"No verificados: {metrics.controls.excluded.no_verificado}",
            "",
            "Etapas",
        ]
    )
    lines.extend(
        f"- {_text(stage.code)} | {_text(stage.name)} | {_label(stage.status)} | "
        f"{_text(stage.started_on)} -> {_text(stage.ended_on or 'En curso')}"
        for stage in detail.stages
    )
    lines.extend(["", "Desvios y seguimiento", f"Total: {metrics.findings.total}"])
    for finding in detail.findings:
        responsible_name = (
            finding.responsible_person_name or finding.responsible_contractor_name or "Sin asignar"
        )
        lines.append(
            f"- {str(finding.id)[:8]} | {_label(finding.status)} | "
            f"{_label(finding.severity_code)} | Responsable: {_text(responsible_name)}"
        )
    lines.extend(
        [
            "",
            "Ultima auditoria: "
            + (
                str(metrics.latest_audit.id)
                if metrics.latest_audit
                else "Aun no hay auditorias realizadas."
            ),
            "Documento generado por H&S Gestion a partir de registros trazables del sistema.",
            "Datos exclusivamente sinteticos. No constituye certificacion legal.",
        ]
    )
    return lines


def _audit_lines(detail: WorksiteDetail, audit_id: object) -> list[str]:
    audit = next((item for item in detail.audits if item.id == audit_id), None)
    if audit is None:
        return ["H&S Gestion - Informe de Auditoria", "Auditoria no visible para este alcance."]
    lines = [
        "H&S Gestion - Informe de Auditoria",
        f"Obra: {detail.code} - {detail.name}",
        f"Jurisdiccion: {detail.jurisdiction}",
        f"Fecha: {_text(audit.audit_date or 'Sin fecha')}",
        f"ID de auditoria: {audit.id}",
        f"Estado: {_label(audit.status)} | Inicio: {_text(audit.started_at)}",
        f"Cierre: {_text(audit.finalized_at or 'En curso')}",
        f"Auditor: {_text(audit.auditor_name or audit.auditor_actor_id or audit.author_id)}",
        f"Funcion: {_label(audit.auditor_function)}",
        f"Responsable profesional: {_text(audit.responsible_professional_name or 'No informado')}",
        "",
        *_responsibility_lines(detail),
        "",
        "Etapas observadas",
    ]
    lines.extend(
        f"- {_text(stage.name)} | {_text(stage.sector or 'Sin sector')} | "
        f"{_text(stage.started_on)} -> {_text(stage.ended_on or 'En curso')}"
        for stage in detail.stages
    )
    lines.extend(["", "Personal y habilitacion"])
    lines.extend(
        f"- {_text(person.display_name)} | {_text(person.role_label)} | "
        f"{_label(person.habilitation_status)}"
        for person in detail.people
    )
    lines.extend(["", *_document_lines(detail), "", *_machine_lines(detail), "", "Checklist"])
    for control in audit.controls:
        lines.append(
            f"{_text(control.catalog_code)} | {_label(control.result)} | "
            f"{_text(control.catalog_title)} | {_text(control.reason or 'Sin observaciones')}"
        )
    lines.extend(["", "Desvios y seguimiento"])
    for finding in sorted(detail.findings, key=lambda item: (item.created_at or "", str(item.id))):
        if finding.audit_id != audit.id:
            continue
        lines.append(
            f"{str(finding.id)[:8]} | {_label(finding.status)} | {_label(finding.severity_code)} | "
            f"Hallazgo: {_text(finding.description)}"
        )
        responsible_name = (
            finding.responsible_person_name or finding.responsible_contractor_name or "Sin asignar"
        )
        lines.append(
            f"  Afectado: {_text(finding.affected_contractor_name or 'Sin empresa')} | "
            f"Responsable: {_text(responsible_name)} | Plazo: {_text(finding.due_at)}"
        )
        for correction in finding.corrections:
            lines.append(
                f"  Correccion: {_text(correction.description)} | "
                f"Evidencia: {_text(correction.evidence_note)} | "
                f"{_text(correction.created_at)}"
            )
        for verification in finding.verifications:
            lines.append(
                f"  Verificacion: {_label(verification.decision)} | {_text(verification.notes)} | "
                f"{_text(verification.created_at)}"
            )
        for event in finding.events:
            lines.append(
                f"  Historial: {_label(event.event_type)} | {_label(event.to_status)} | "
                f"{_text(event.detail or 'Sin detalle')} | {_text(event.created_at)}"
            )
    lines.extend(
        [
            "",
            "Documento generado por H&S Gestion a partir de registros trazables del sistema.",
            "Demo funcional - datos sinteticos - no constituye certificacion legal.",
        ]
    )
    return lines


def build_worksite_report_pdf(detail: WorksiteDetail) -> bytes:
    return _build_pdf(_report_lines(detail))


def build_audit_report_pdf(detail: WorksiteDetail, audit_id: object) -> bytes:
    return _build_pdf(_audit_lines(detail, audit_id))


def _build_pdf(lines: list[str]) -> bytes:
    page_size = 37
    pages = [lines[index : index + page_size] for index in range(0, len(lines), page_size)] or [[]]
    page_count = len(pages)
    page_bodies: list[bytes] = []
    content_bodies: list[bytes] = []
    for page_number, page_lines in enumerate(pages, start=1):
        commands = [b"BT", b"/F1 10 Tf", b"50 790 Td"]
        for index, line in enumerate([*page_lines, f"Pagina {page_number} de {page_count}"]):
            if index:
                commands.append(b"0 -20 Td")
            commands.extend([_pdf_literal(line), b"Tj"])
        commands.append(b"ET")
        stream = b"\n".join(commands)
        content_bodies.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    first_content = 4 + page_count
    for index in range(page_count):
        content_number = first_content + index
        page_bodies.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {3 + page_count} 0 R >> >> "
                f"/Contents {content_number} 0 R >>"
            ).encode("ascii")
        )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>".encode("ascii"),
        (
            f"<< /Type /Pages /Kids "
            f"[{' '.join(f'{3 + index} 0 R' for index in range(page_count))}] "
            f"/Count {page_count} >>"
        ).encode("ascii"),
        *page_bodies,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        *content_bodies,
    ]
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode("ascii"))
        result.extend(body)
        result.extend(b"\nendobj\n")
    xref_offset = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    result.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(result)


def _pdf_literal(value: object) -> bytes:
    escaped = _text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")
