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


def _pdf_literal(value: object) -> bytes:
    escaped = _text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")


def _report_lines(detail: WorksiteDetail) -> list[str]:
    metrics = detail.metrics
    lines = [
        "H&S Gestion - Reporte sintetico de obra",
        f"Obra: {detail.code} - {detail.name}",
        f"Jurisdiccion: {detail.jurisdiction} | Estado: {detail.status}",
        "",
        "Documentacion y vencimientos",
        f"Total: {metrics.documents.total}",
    ]
    lines.extend(
        f"{status}: {count}"
        for status, count in sorted(
            metrics.documents.by_status.items(), key=lambda item: _text(item[0])
        )
    )
    lines.extend(
        [
            "",
            "Auditoria",
            f"Auditorias registradas: {len(detail.audits)}",
            f"Controles CUMPLE: {metrics.controls.numerator}",
            f"Controles evaluados: {metrics.controls.denominator}",
            f"Controles NO_APLICA: {metrics.controls.excluded.no_aplica}",
            f"Controles NO_VERIFICADO: {metrics.controls.excluded.no_verificado}",
            "",
            "Desvios y cierre",
            f"Total: {metrics.findings.total}",
        ]
    )
    lines.extend(
        f"{status}: {count}"
        for status, count in sorted(
            metrics.findings.by_status.items(), key=lambda item: _text(item[0])
        )
    )
    for finding in detail.findings:
        lines.append(
            f"- {_text(finding.status)} | {_text(finding.severity_code)} | {_text(finding.title)}"
        )
    lines.extend(
        [
            "",
            f"Maquinarias: {metrics.machines.total}",
            f"Generado desde el estado persistido: {metrics.calculated_at.isoformat()}",
            "Datos exclusivamente sinteticos. No constituye certificacion legal.",
        ]
    )
    return lines


def build_worksite_report_pdf(detail: WorksiteDetail) -> bytes:
    """Build a valid one-page PDF without adding a worker or a dependency."""

    commands = [b"BT", b"/F1 14 Tf", b"50 790 Td"]
    for index, line in enumerate(_report_lines(detail)):
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
