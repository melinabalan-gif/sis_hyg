import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import HomePage from "../../app/page";
import { PROTOTYPE_NOTICE } from "../../src/components/environment-banner";

const worksite = {
  id: "10000000-0000-4000-8000-000000000001",
  code: "OBR-001",
  name: "Obra Piloto Norte",
  jurisdiction: "Provincia sintética",
  status: "ACTIVE",
  version: 1,
};

const emptyMetrics = {
  documents: {
    total: 0,
    by_status: {
      FALTANTE: 0,
      PENDIENTE: 0,
      RECHAZADO: 0,
      POR_VENCER: 0,
      VENCIDO: 0,
      VIGENTE: 0,
    },
  },
  findings: {
    total: 0,
    by_status: {
      ABIERTO: 0,
      EN_CORRECCION: 0,
      PENDIENTE_VERIFICACION: 0,
      CERRADO: 0,
    },
    overdue: 0,
  },
  machines: {
    total: 0,
    by_status: {
      OPERATIVA: 0,
      CON_OBSERVACIONES: 0,
      FUERA_DE_SERVICIO: 0,
    },
  },
  latest_audit: null,
  controls: {
    audit_id: null,
    numerator: 0,
    denominator: 0,
    ratio: null,
    excluded: { no_aplica: 0, no_verificado: 0 },
  },
  calculated_at: "2026-09-04T15:00:00Z",
};

const detail = {
  ...worksite,
  stages: [],
  contractors: [],
  people: [],
  documents: [],
  machines: [],
  audits: [],
  findings: [],
  metrics: emptyMetrics,
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HomePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("expone inequívocamente el alcance sintético y el inicio del flujo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );

    render(<HomePage />);

    expect(screen.getByText(PROTOTYPE_NOTICE)).toBeVisible();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: /creá o abrí una obra/i }),
    ).toBeVisible();
    expect(
      await screen.findByText(/creá la primera obra sintética/i),
    ).toBeVisible();
    expect(screen.getByLabelText(/actuar como/i)).toHaveValue("tecnico");
  });

  it("crea, abre y navega una obra persistida", async () => {
    let created = false;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/api/v1/worksites") && init?.method === "POST") {
          created = true;
          expect(init.headers).toMatchObject({ "X-Pilot-Actor": "tecnico" });
          return jsonResponse(worksite, 201);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`))
          return jsonResponse(detail);
        if (path.endsWith("/api/v1/worksites"))
          return jsonResponse(created ? [worksite] : []);
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await screen.findByText(/creá la primera obra sintética/i);
    await user.type(screen.getByLabelText("Código"), "OBR-001");
    await user.type(screen.getByLabelText("Nombre"), "Obra Piloto Norte");
    await user.type(screen.getByLabelText("País"), "Argentina");
    await user.type(screen.getByLabelText("Provincia"), "Provincia sintética");
    await user.type(screen.getByLabelText("Municipio"), "Municipio sintético");
    await user.click(screen.getByRole("button", { name: /crear y abrir/i }));

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Obra Piloto Norte",
      }),
    ).toBeVisible();
    expect(screen.getByText(/obra creada y abierta/i)).toBeVisible();
    expect(screen.getByText(/no hay documentos registrados/i)).toBeVisible();
    expect(screen.getByText("Aún no hay auditorías realizadas")).toBeVisible();
    expect(screen.getByText(/no hay auditorías registradas/i)).toBeVisible();
    await user.click(screen.getByRole("tab", { name: /04.*contratistas/i }));
    expect(
      screen.getByRole("heading", { level: 2, name: "Contratistas" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/worksites",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("reconcilia el dashboard con estados visibles y enlaza al detalle", async () => {
    const metrics = {
      ...emptyMetrics,
      documents: {
        total: 2,
        by_status: {
          ...emptyMetrics.documents.by_status,
          POR_VENCER: 1,
          VIGENTE: 1,
        },
      },
      findings: {
        total: 2,
        by_status: {
          ...emptyMetrics.findings.by_status,
          ABIERTO: 1,
          CERRADO: 1,
        },
        overdue: 1,
      },
      machines: {
        total: 2,
        by_status: {
          ...emptyMetrics.machines.by_status,
          OPERATIVA: 1,
          FUERA_DE_SERVICIO: 1,
        },
      },
      latest_audit: {
        id: "20000000-0000-4000-8000-000000000001",
        status: "EN_CURSO",
        started_at: "2026-09-04T15:00:00Z",
        finalized_at: null,
      },
      controls: {
        audit_id: "20000000-0000-4000-8000-000000000001",
        numerator: 0,
        denominator: 0,
        ratio: null,
        excluded: { no_aplica: 2, no_verificado: 1 },
      },
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
        return jsonResponse({ ...detail, metrics });
      }
      if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
      throw new Error(`Ruta inesperada: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));

    expect(
      screen.getByText(
        (_content, element) =>
          element?.textContent?.replace(/\s+/g, " ").trim() ===
          "2 documentos visibles",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        (_content, element) =>
          element?.textContent?.replace(/\s+/g, " ").trim() ===
          "Vencidos sin cerrar: 1",
      ),
    ).toBeVisible();
    expect(screen.getByText("Aún no hay auditorías realizadas")).toBeVisible();
    expect(
      screen.getByText(/excluye "no aplica" \(2\) y "no verificado" \(1\)/i),
    ).toBeVisible();

    await user.click(
      screen.getAllByRole("button", { name: /ver detalle/i })[0],
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "Documentación" }),
    ).toBeVisible();
  });

  it("informa un error del backend sin perder el formulario", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/api/v1/worksites") && init?.method === "POST") {
          return jsonResponse(
            { detail: "El código ya existe en la organización." },
            409,
          );
        }
        return jsonResponse([]);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await screen.findByText(/creá la primera obra sintética/i);
    await user.type(screen.getByLabelText("Código"), "OBR-001");
    await user.type(screen.getByLabelText("Nombre"), "Duplicada");
    await user.type(screen.getByLabelText("País"), "Argentina");
    await user.type(screen.getByLabelText("Provincia"), "Provincia sintética");
    await user.type(screen.getByLabelText("Municipio"), "Municipio sintético");
    await user.click(screen.getByRole("button", { name: /crear y abrir/i }));

    expect(await screen.findByText(/el código ya existe/i)).toHaveClass(
      "message--error",
    );
    expect(screen.getByLabelText("Código")).toHaveValue("OBR-001");
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /crear y abrir/i }),
      ).toBeEnabled(),
    );
  });

  it("renderiza el checklist completo y actualiza su progreso al responder", async () => {
    const auditId = "20000000-0000-4000-8000-000000000001";
    const catalog = [
      {
        catalog_code: "SYN-CIRCULACION-001",
        catalog_title: "Circulación sintética",
      },
      { catalog_code: "SYN-EPP-001", catalog_title: "EPP sintético" },
      { catalog_code: "SYN-ORDEN-001", catalog_title: "Orden sintético" },
    ];
    const answered = new Set(["SYN-ORDEN-001"]);
    const auditDetail = () => ({
      ...detail,
      audits: [
        {
          id: auditId,
          status: "EN_CURSO",
          started_at: "2026-09-03T15:00:00Z",
          finalized_at: null,
          available_controls: catalog,
          controls: catalog
            .filter((item) => answered.has(item.catalog_code))
            .map((item, index) => ({
              id: `30000000-0000-4000-8000-00000000000${index + 1}`,
              ...item,
              result: "CUMPLE",
              reason: null,
              finding_id: null,
            })),
        },
      ],
    });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith(`/api/v1/audits/${auditId}/controls`)) {
          const payload = JSON.parse(String(init?.body)) as {
            catalog_code: string;
          };
          answered.add(payload.catalog_code);
          return jsonResponse({}, 201);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse(auditDetail());
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.selectOptions(screen.getByLabelText(/actuar como/i), "auditor");
    await user.click(
      await screen.findByRole("tab", { name: /08.*auditoría/i }),
    );

    expect(screen.getByText("Circulación sintética")).toBeVisible();
    expect(screen.getByText("EPP sintético")).toBeVisible();
    expect(screen.getByText("Orden sintético")).toBeVisible();
    expect(
      screen.getByRole("progressbar", {
        name: "1 de 3 controles respondidos",
      }),
    ).toBeVisible();

    await user.click(
      screen.getAllByRole("button", { name: /registrar control/i })[0],
    );

    expect(
      await screen.findByRole("progressbar", {
        name: "2 de 3 controles respondidos",
      }),
    ).toBeVisible();
    expect(screen.getAllByText("Cumple").length).toBeGreaterThan(0);
  });

  it("permite registrar etapas simultáneas y las muestra en la línea temporal", async () => {
    const stages: Array<Record<string, string | null>> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith(`/api/v1/worksites/${worksite.id}/stages`)) {
          const payload = JSON.parse(String(init?.body)) as Record<
            string,
            string
          >;
          const stage = {
            id: `60000000-0000-4000-8000-00000000000${stages.length + 1}`,
            worksite_id: worksite.id,
            ...payload,
            ended_on: payload.ended_on ?? null,
            sector: payload.sector ?? null,
            notes: payload.notes ?? null,
            created_at: "2026-09-03T15:00:00Z",
            updated_at: "2026-09-03T15:00:00Z",
          };
          stages.push(stage);
          return jsonResponse(stage, 201);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse({ ...detail, stages });
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.click(await screen.findByRole("tab", { name: /03.*etapas/i }));

    const codeFields = screen.getAllByLabelText("Código");
    const nameFields = screen.getAllByLabelText("Nombre");
    await user.type(codeFields.at(-1)!, "STG-001");
    await user.selectOptions(nameFields.at(-1)!, "Preparación");
    await user.type(screen.getByLabelText("Inicio"), "2026-09-01");
    await user.click(screen.getByRole("button", { name: /guardar etapa/i }));
    expect((await screen.findAllByText("Preparación")).at(-1)).toBeVisible();

    await user.type(screen.getAllByLabelText("Código").at(-1)!, "STG-002");
    await user.selectOptions(
      screen.getAllByLabelText("Nombre").at(-1)!,
      "Montaje",
    );
    fireEvent.change(screen.getByLabelText("Inicio"), {
      target: { value: "2026-09-15" },
    });
    await user.click(screen.getByRole("button", { name: /guardar etapa/i }));

    expect((await screen.findAllByText("Montaje")).at(-1)).toBeVisible();
    expect(screen.getByText("2", { selector: ".counter" })).toBeVisible();
  });

  it("muestra historial y registra una nueva versión manteniendo la obra", async () => {
    const documentId = "70000000-0000-0000-0000-000000000001";
    let currentDocument = {
      id: documentId,
      subject_kind: "WORKSITE",
      subject_id: worksite.id,
      subject_name: worksite.name,
      title: "Seguro inicial",
      document_type: "SEGURO",
      review_status: "APROBADO",
      status: "POR_VENCER",
      valid_from: "2026-09-01",
      expires_on: "2026-09-05",
      notes: "Inicial",
      version: 1,
      versions: [
        {
          id: "71000000-0000-0000-0000-000000000001",
          version_number: 1,
          title: "Seguro inicial",
          document_type: "SEGURO",
          review_status: "APROBADO",
          valid_from: "2026-09-01",
          expires_on: "2026-09-05",
          notes: "Inicial",
          actor_id: "72000000-0000-0000-0000-000000000001",
          created_at: "2026-09-03T15:00:00Z",
        },
      ],
      created_at: "2026-09-03T15:00:00Z",
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith(`/documents/${documentId}/versions`)) {
          const payload = JSON.parse(String(init?.body)) as Record<
            string,
            string
          >;
          currentDocument = {
            ...currentDocument,
            title: payload.title,
            expires_on: payload.expires_on,
            version: 2,
            versions: [
              {
                ...currentDocument.versions[0],
                id: "73000000-0000-0000-0000-000000000001",
                version_number: 2,
                title: payload.title,
                expires_on: payload.expires_on,
                notes: payload.notes,
                created_at: "2026-09-04T15:00:00Z",
              },
              ...currentDocument.versions,
            ],
          };
          return jsonResponse(currentDocument, 201);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse({ ...detail, documents: [currentDocument] });
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.click(
      await screen.findByRole("tab", { name: /06.*documentación/i }),
    );

    expect(screen.getAllByText(/versión 1/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Historial (1 versiones)")).toBeVisible();
    await user.type(
      screen.getByLabelText("Título de la versión"),
      "Seguro renovado",
    );
    await user.type(screen.getByLabelText("Tipo de la versión"), "SEGURO");
    await user.type(screen.getAllByLabelText("Vence el").at(-1)!, "2026-12-31");
    await user.type(
      screen.getAllByLabelText("Nota sintética").at(-1)!,
      "Renovación",
    );
    await user.click(
      screen.getByRole("button", { name: /registrar versión/i }),
    );

    expect(await screen.findByText(/nueva versión registrada/i)).toBeVisible();
    expect(screen.getAllByText(/versión 2/i).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/worksites/${worksite.id}/documents/${documentId}/versions`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("muestra el historial de maquinarias y registra una reinspección", async () => {
    const machineId = "80000000-0000-0000-0000-000000000001";
    let machine = {
      id: machineId,
      assignment_id: "81000000-0000-0000-0000-000000000001",
      internal_code: "MAQ-001",
      description: "Autoelevador sintético",
      status: "OPERATIVA",
      version: 1,
      contractor_id: null,
      inspection_reason: "Inspección inicial aprobada",
      inspected_at: "2026-09-03T15:00:00Z",
      started_on: "2026-09-01",
      ended_on: null,
      inspections: [
        {
          id: "82000000-0000-0000-0000-000000000001",
          resulting_status: "OPERATIVA",
          reason: "Inspección inicial aprobada",
          actor_id: "83000000-0000-0000-0000-000000000001",
          inspected_at: "2026-09-03T15:00:00Z",
        },
      ],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith(`/machines/${machineId}/inspections`)) {
          const payload = JSON.parse(String(init?.body)) as {
            resulting_status: string;
            reason: string;
          };
          expect(payload).toEqual({
            resulting_status: "FUERA_DE_SERVICIO",
            reason: "Falla crítica detectada",
            checklist: {
              brakes: "CUMPLE",
              lights: "CUMPLE",
              reverse_alarm: "CUMPLE",
              horn: "CUMPLE",
              tires: "CUMPLE",
              mirrors: "CUMPLE",
              seat_belt: "CUMPLE",
              fire_extinguisher: "CUMPLE",
              warning_lights: "CUMPLE",
              leaks: "CUMPLE",
              guards: "CUMPLE",
              signage: "CUMPLE",
              specific_devices: "CUMPLE",
            },
          });
          machine = {
            ...machine,
            status: payload.resulting_status,
            version: 2,
            inspections: [
              {
                ...machine.inspections[0],
                id: "84000000-0000-0000-0000-000000000001",
                resulting_status: payload.resulting_status,
                reason: payload.reason,
              },
              ...machine.inspections,
            ],
          };
          return jsonResponse(machine, 201);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse({ ...detail, machines: [machine] });
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.click(
      await screen.findByRole("tab", { name: /07.*maquinarias/i }),
    );

    expect(
      screen.getByText("Versión 1 · Última inspección registrada"),
    ).toBeVisible();
    await user.click(screen.getByText("Historial de inspecciones (1)"));
    expect(screen.getByText("Inspección inicial aprobada")).toBeVisible();
    await user.click(screen.getByText("Registrar reinspección o transición"));

    await user.selectOptions(
      screen.getByLabelText(/nuevo estado/i),
      "FUERA_DE_SERVICIO",
    );
    await user.type(
      screen.getByLabelText("Motivo de reinspección"),
      "Falla crítica detectada",
    );
    await user.click(
      screen.getByRole("button", { name: /registrar inspección/i }),
    );

    expect(
      await screen.findByText(
        /reinspección registrada; estado y versión actualizados/i,
      ),
    ).toBeVisible();
    expect(
      screen.getByText("Versión 2 · Última inspección registrada"),
    ).toBeVisible();
    expect(
      screen.getByText(/fuera de servicio: no debe operar/i),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/worksites/${worksite.id}/machines/${machineId}/inspections`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});
