"""Small synchronous PDF renderer for the synthetic pilot report."""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from hys_api.modules.pilot.schemas import WorksiteDetail


def _text(value: object) -> str:
    """Convert report values to the ASCII subset supported by Helvetica."""

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
    "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL": "Licenciado H&S de contratista principal",
    "RESPONSABLE_HYS_PROYECTO": "Licenciado H&S del proyecto",
    "TECNICO_HYS_CONTRATISTA_PRINCIPAL": "Tecnico H&S de contratista principal",
    "VENCIDO": "Vencido",
    "VIGENTE": "Vigente",
}


def _label(value: object) -> str:
    if value is None:
        return "Sin informar"
    raw = value.value if isinstance(value, StrEnum) else str(value)
    return _LABELS.get(raw, raw.replace("_", " ").capitalize())


def _pdf_literal(value: object) -> bytes:
    escaped = _text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")


def _report_lines(detail: WorksiteDetail) -> list[str]:
    metrics = detail.metrics
    lines = [
        "H&S Gestion - Reporte Ejecutivo de Obra",
        f"Obra: {detail.code} - {detail.name}",
        f"Jurisdiccion: {detail.jurisdiction} | Estado: {_label(detail.status)}",
        "Organizacion: Piloto H&S - datos sinteticos | "
        f"Generado: {metrics.calculated_at.isoformat()}",
        "",
            "Documentacion y vencimientos",
            f"Total: {metrics.documents.total}",
    ]
    lines.extend(
        f"{_label(status)}: {count}"
        for status, count in sorted(
            metrics.documents.by_status.items(), key=lambda item: _text(item[0])
        )
    )
    lines.extend(["", f"Contratistas: {len(detail.contractors)}"])
    lines.extend(
        f"- {_text(contractor.legal_name)} | "
        f"{_label(contractor.participation_type or 'CONTRACTOR')}"
        for contractor in detail.contractors
    )
    lines.extend(["", f"Personal registrado: {len(detail.people)}"])
    lines.extend(
        f"- {_text(person.display_name)} | {_label(person.habilitation_status)}"
        for person in detail.people
    )
    lines.extend(
        [
            "",
            "Auditoria",
            f"Auditorias registradas: {len(detail.audits)}",
            f"Controles que cumplen: {metrics.controls.numerator}",
            f"Controles evaluados: {metrics.controls.denominator}",
            f"Controles no aplicables: {metrics.controls.excluded.no_aplica}",
            f"Controles no verificados: {metrics.controls.excluded.no_verificado}",
            "",
            "Desvios y cierre",
            f"Total: {metrics.findings.total}",
        ]
    )
    lines.extend(
        f"{_label(status)}: {count}"
        for status, count in sorted(
            metrics.findings.by_status.items(), key=lambda item: _text(item[0])
        )
    )
    for finding in detail.findings:
        lines.append(
            f"- {_label(finding.status)} | {_label(finding.severity_code)} | {_text(finding.title)}"
        )
    lines.extend(
        [
            "",
            "Maquinarias por estado: "
            + ", ".join(
                f"{_label(status)} {count}"
                for status, count in sorted(metrics.machines.by_status.items())
            ),
            "Ultima auditoria: "
            f"{metrics.latest_audit.id if metrics.latest_audit else 'Aun no hay '
            'auditorias realizadas.'}",
            "Documento generado por H&S Gestion a partir de registros trazables del sistema.",
            "Datos exclusivamente sinteticos. No constituye certificacion legal.",
        ]
    )
    return lines


def _audit_lines(detail: WorksiteDetail, audit_id: object) -> list[str]:
    metrics = detail.metrics
    audit = next((item for item in detail.audits if item.id == audit_id), None)
    if audit is None:
        return ["H&S Gestion - Informe de Auditoria", "Auditoria no visible para este alcance."]
    lines = [
        "H&S Gestion - Informe de Auditoria",
        f"Obra: {detail.code} - {detail.name}",
        f"Jurisdiccion: {detail.jurisdiction}",
        f"ID de auditoria: {audit.id}",
        f"Estado: {_label(audit.status)} | Inicio: {audit.started_at.isoformat()}",
        f"Cierre: {audit.finalized_at.isoformat() if audit.finalized_at else 'En curso'}",
        f"Auditor: {audit.auditor_name or audit.auditor_actor_id or audit.author_id}",
        f"Funcion: {_label(audit.auditor_function or 'No informada')}",
        f"Responsable profesional: {audit.responsible_professional_name or 'No informado'}",
        "",
        "Checklist",
    ]
    lines.extend(
        [
            "",
            f"Personal presente: {len(detail.people)}",
            f"Documentacion visible: {metrics.documents.total}",
            f"Maquinarias visibles: {metrics.machines.total}",
            "",
        ]
    )
    for control in audit.controls:
        lines.append(
            f"{control.catalog_code} | {_label(control.result)} | {_text(control.catalog_title)} | "
            f"{_text(control.reason or 'Sin observaciones')}"
        )
    lines.extend(["", "Desvios y seguimiento"])
    for finding in detail.findings:
        if finding.audit_id != audit.id:
            continue
        lines.append(
            f"{str(finding.id)[:8]} | {_label(finding.status)} | {_label(finding.severity_code)} | "
            f"{_text(finding.description)}"
        )
        for correction in finding.corrections:
            lines.append(f"  Correccion: {_text(correction.description)}")
            lines.append(f"  Evidencia: {_text(correction.evidence_note)}")
    lines.extend(
        [
            "",
            "Documento generado por H&S Gestion a partir de registros trazables del sistema.",
            "Demo funcional - datos sinteticos - no constituye certificacion legal.",
        ]
    )
    return lines


def build_worksite_report_pdf(detail: WorksiteDetail) -> bytes:
    """Build a valid one-page PDF without adding a worker or a dependency."""

    return _build_pdf(_report_lines(detail))


def build_audit_report_pdf(detail: WorksiteDetail, audit_id: object) -> bytes:
    """Build a traceable, synthetic report for one historical audit."""

    return _build_pdf(_audit_lines(detail, audit_id))


def _build_pdf(lines: list[str]) -> bytes:
    commands = [b"BT", b"/F1 14 Tf", b"50 790 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append(b"0 -18 Td")
        commands.extend([_pdf_literal(line), b"Tj"])
    commands.append(b"ET")
    stream = b"\n".join(commands)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
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
