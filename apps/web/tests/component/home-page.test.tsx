import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
  functional_assignments: [
    {
      id: "11000000-0000-4000-8000-000000000001",
      worksite_id: worksite.id,
      actor_id: "00000000-0000-4000-8000-000000000001",
      actor_key: "auditor",
      actor_label: "Auditor",
      person_id: null,
      person_name: null,
      profession_code: "TECNICO_HYS",
      function_code: "AUDITOR",
      represented_contractor_id: null,
      represented_contractor_name: null,
      delegated_by_assignment_id: null,
      permission_scope: "WORKSITE",
      valid_from: "2026-09-01",
      valid_to: null,
      version: 1,
    },
  ],
  audits: [],
  findings: [],
  metrics: emptyMetrics,
};

const responsibilityDetail = {
  ...detail,
  contractors: [
    {
      id: "12000000-0000-0000-0000-000000000001",
      legal_name: "Contratista principal sintética",
      trade: "Construcción",
      participation_type: "PRINCIPAL",
    },
  ],
  people: [
    {
      id: "13000000-0000-0000-0000-000000000001",
      display_name: "Licenciada de proyecto",
      contractor_id: null,
      role_label: "Licenciada H&S",
      profession_code: "LICENCIADO_HYS",
    },
    {
      id: "13000000-0000-0000-0000-000000000002",
      display_name: "Técnico auditor",
      contractor_id: "12000000-0000-0000-0000-000000000001",
      role_label: "Auditor",
      profession_code: "TECNICO_HYS",
    },
  ],
  functional_assignments: [
    {
      ...detail.functional_assignments[0],
      id: "11000000-0000-0000-0000-000000000001",
      person_id: "13000000-0000-0000-0000-000000000002",
      person_name: "Técnico auditor",
      delegated_by_assignment_id: "11000000-0000-0000-0000-000000000002",
      assigned_by_label: "Licenciada de proyecto",
    },
    {
      ...detail.functional_assignments[0],
      id: "11000000-0000-0000-0000-000000000002",
      actor_id: "00000000-0000-4000-8000-000000000003",
      actor_key: "responsable",
      actor_label: "Licenciado H&S del proyecto",
      person_id: "13000000-0000-0000-0000-000000000001",
      person_name: "Licenciada de proyecto",
      profession_code: "LICENCIADO_HYS",
      function_code: "RESPONSABLE_HYS_PROYECTO",
      assigned_by_label: "Licenciada de proyecto",
    },
  ],
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
      screen.getByRole("heading", {
        level: 1,
        name: /abrí una obra existente/i,
      }),
    ).toBeVisible();
    expect(
      await screen.findByText(/seleccioná una obra para iniciar/i),
    ).toBeVisible();
    expect(screen.getByLabelText(/actuar como/i)).toHaveValue("tecnico");
  });

  it("expone sólo las identidades seleccionables del piloto", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );

    render(<HomePage />);

    const selector = await screen.findByLabelText(/actuar como/i);
    expect(
      Array.from(selector.querySelectorAll("option")).map(
        (option) => option.value,
      ),
    ).toEqual([
      "tecnico",
      "auditor",
      "responsable",
      "licenciado-contratista-principal",
      "contratista-principal",
    ]);
  });

  it("separa el perfil activo de su información secundaria en el encabezado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );

    render(<HomePage />);

    const header = screen.getByRole("banner");
    const context = header.querySelector(".actor-context");

    expect(context).toBeInTheDocument();
    expect(context?.querySelector("strong")).toHaveTextContent(
      "Técnico H&S de contratista principal",
    );
    expect(context?.querySelector("span")).toHaveTextContent(
      "Perfil operativo del piloto",
    );
    expect(context?.classList.contains("actor-context")).toBe(true);
    expect(header.querySelector(".actor-switcher")).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText(/actuar como/i),
      "responsable",
    );

    expect(context?.querySelector("strong")).toHaveTextContent(
      "Licenciado H&S del proyecto",
    );
    expect(context?.querySelector("span")).toHaveTextContent(
      "Perfil operativo del piloto",
    );
  });

  it("mantiene la creación sólo en el formulario principal de los perfiles autorizados", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );
    const user = userEvent.setup();

    render(<HomePage />);
    const selector = await screen.findByLabelText(/actuar como/i);

    for (const label of [
      "Preparar el legajo",
      "Ejecutar el control",
      "Corregir y verificar",
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }

    for (const actor of ["tecnico", "auditor"] as const) {
      await user.selectOptions(selector, actor);
      expect(
        screen.queryByRole("button", { name: "Nueva obra" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /crear y abrir/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /abrí una obra existente/i }),
      ).toBeVisible();
    }

    for (const actor of [
      "responsable",
      "licenciado-contratista-principal",
      "contratista-principal",
    ] as const) {
      await user.selectOptions(selector, actor);
      expect(
        screen.queryByRole("button", { name: "Nueva obra" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /crear y abrir/i }),
      ).toBeEnabled();
      expect(
        screen.getByRole("heading", { name: /creá o abrí una obra/i }),
      ).toBeVisible();
    }
  });

  it("muestra responsables y mantiene la pestaña en solo lectura para Técnico", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
        return jsonResponse(responsibilityDetail);
      }
      if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
      throw new Error(`Ruta inesperada: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.click(
      await screen.findByRole("tab", { name: /responsables/i }),
    );

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Responsables de la obra",
      }),
    ).toBeVisible();
    expect(screen.getAllByText("Técnico auditor")[0]).toBeVisible();
    expect(
      screen.getAllByText("Delegado por: Licenciada de proyecto")[0],
    ).toBeVisible();
    expect(screen.queryByText("Identidad sintética")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cambiar auditor" }),
    ).not.toBeInTheDocument();
  });

  it("muestra los dos legajos técnicos sin formulario genérico", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
        return jsonResponse(detail);
      }
      if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
      throw new Error(`Ruta inesperada: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.selectOptions(
      screen.getByLabelText(/actuar como/i),
      "responsable",
    );
    await user.click(
      await screen.findByRole("tab", { name: /legajos técnicos/i }),
    );

    expect(
      screen.getByRole("heading", { name: "Legajos Técnicos" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Legajo Técnico - Contratista Principal",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Legajo Técnico - Proyecto" }),
    ).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Ver legajo" })).toHaveLength(
      2,
    );
    expect(
      screen.getByText(/documentación propia de la empresa principal/i),
    ).toBeVisible();
    expect(screen.getAllByText("Pendiente")).toHaveLength(1);
    expect(screen.getByText("Sin documentación")).toBeVisible();
    expect(
      screen.queryByText("Asociado conceptualmente a la Contratista Principal"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Documentación de contratistas" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Título")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tipo")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Sujeto")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/la vigencia se deriva/i),
    ).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[1]);
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Legajo Técnico - Proyecto",
      }),
    ).toBeVisible();
    expect(screen.getByLabelText("Auditor asignado")).toBeEnabled();
    expect(screen.getByLabelText("Profesión del auditor")).toBeEnabled();
    expect(
      screen.getByLabelText("Carga horaria semanal del auditor"),
    ).toBeEnabled();
    for (const component of [
      "Memoria descriptiva H&S",
      "Riesgos por etapa",
      "Medidas preventivas previstas",
      "Programa de Seguridad de Proyecto",
      "Planos H&S de Proyecto",
    ]) {
      expect(screen.getByRole("heading", { name: component })).toBeVisible();
    }
    expect(screen.getAllByRole("button", { name: "Completar" })).toHaveLength(
      4,
    );
    expect(screen.getByRole("button", { name: "Adjuntar" })).toBeVisible();
    expect(screen.queryByText(/pendiente/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/documentos requeridos/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/documentos cargados/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/estado del legajo/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/progreso/i)).not.toBeInTheDocument();
    for (const oldTitle of [
      "Información del proyecto",
      "Planificación H&S",
      "Implantación y servicios",
      "Autorizaciones y condiciones de inicio",
    ]) {
      expect(screen.queryByText(oldTitle)).not.toBeInTheDocument();
    }
    expect(screen.queryByLabelText("Título")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /volver a legajos/i }));
    await user.selectOptions(screen.getByLabelText(/actuar como/i), "tecnico");
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[1]);
    for (const label of [
      "Auditor asignado",
      "Profesión del auditor",
      "Carga horaria semanal del auditor",
    ]) {
      expect(screen.getByText(label, { selector: "dt" })).toBeVisible();
    }
    expect(screen.getAllByText("Sin especificar")).toHaveLength(2);
    expect(screen.getByText("Sin asignar")).toBeVisible();
    expect(screen.queryByLabelText("Auditor asignado")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Profesión del auditor"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Carga horaria semanal del auditor"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /volver a legajos/i }));
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Legajo Técnico - Contratista Principal",
      }),
    ).toBeVisible();
    for (const component of [
      "Aviso de Obra",
      "RAR",
      "Entrega de credenciales",
      "Visitas ART",
      "Programa de Seguridad",
      "Capacitaciones",
      "Matrícula del Licenciado H&S responsable",
      "Carga horaria semanal",
      "Memoria descriptiva de la obra",
      "Plano de obrador",
      "Puesta a tierra",
      "Registro de visitas del Licenciado H&S de la Contratista Principal",
      "Servicios auxiliares del obrador",
      "Baños",
      "Vestuario",
      "Comedor",
      "Tablero eléctrico",
      "Extintores",
    ]) {
      expect(screen.getAllByText(component)[0]).toBeVisible();
    }
    const auxiliarySection = screen
      .getByText("Servicios auxiliares del obrador")
      .closest("li");
    expect(auxiliarySection).toBeInTheDocument();
    expect(auxiliarySection).not.toHaveTextContent("Pendiente");
    expect(auxiliarySection).not.toHaveTextContent("Sin información cargada");
    expect(auxiliarySection).not.toHaveTextContent("Cargar");
    expect(screen.getAllByText("Presencia o disponibilidad")).toHaveLength(1);
    expect(
      auxiliarySection?.querySelectorAll('input[type="radio"]'),
    ).toHaveLength(10);
    expect(
      screen
        .getAllByRole("radio")
        .every((radio) => !(radio as HTMLInputElement).checked),
    ).toBe(true);
    expect(screen.queryByLabelText("Título")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Resumen preparado para una futura acción"),
    ).not.toBeInTheDocument();
    expect(
      screen
        .getByText("Matrícula del Licenciado H&S responsable")
        .closest("li"),
    ).not.toHaveTextContent("Cargar");
    expect(
      screen.getByText("Carga horaria semanal", { exact: true }).closest("li"),
    ).not.toHaveTextContent("Cargar");
  });

  it("permite cambiar la disponibilidad de servicios auxiliares al equipo H&S de la contratista principal", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
        return jsonResponse(detail);
      }
      if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
      throw new Error(`Ruta inesperada: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.click(
      await screen.findByRole("tab", { name: /legajos técnicos/i }),
    );
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);

    const bathrooms = screen.getByRole("group", {
      name: "Baños: presencia o disponibilidad",
    });
    await user.click(within(bathrooms).getByRole("radio", { name: "Sí" }));
    expect(within(bathrooms).getByRole("radio", { name: "Sí" })).toBeChecked();
  });

  it("mantiene los servicios auxiliares en solo lectura para Auditor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse(detail);
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      }),
    );
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.selectOptions(screen.getByLabelText(/actuar como/i), "auditor");
    await user.click(
      await screen.findByRole("tab", { name: /legajos técnicos/i }),
    );
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);

    expect(
      screen.queryByRole("group", {
        name: "Baños: presencia o disponibilidad",
      }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText("Sin seleccionar")).toHaveLength(5);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });

  it("separa la edición del legajo de proyecto y el de la contratista principal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse(detail);
        }
        if (path.endsWith("/api/v1/worksites")) return jsonResponse([worksite]);
        throw new Error(`Ruta inesperada: ${path}`);
      }),
    );
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.selectOptions(
      screen.getByLabelText(/actuar como/i),
      "responsable",
    );
    await user.click(
      await screen.findByRole("tab", { name: /legajos técnicos/i }),
    );

    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[1]);
    expect(screen.getAllByRole("button", { name: "Completar" })).toHaveLength(
      4,
    );
    expect(screen.getByRole("button", { name: "Adjuntar" })).toBeVisible();
    expect(screen.queryByText(/modo consulta/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /volver a legajos/i }));
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);
    expect(
      screen.queryByRole("button", { name: "Completar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Adjuntar" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/modo consulta/i)).toBeVisible();
  });

  it("abre un formulario específico y cambia un responsable sin formulario genérico", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (
          path.includes("/functional-assignments/") &&
          path.endsWith("/change")
        ) {
          expect(init?.method).toBe("POST");
          expect(JSON.parse(String(init?.body))).toMatchObject({
            actor_id: "00000000-0000-4000-8000-000000000001",
            person_id: "13000000-0000-0000-0000-000000000002",
            delegated_by_assignment_id: "11000000-0000-0000-0000-000000000002",
          });
          return jsonResponse({}, 200);
        }
        if (path.endsWith(`/api/v1/worksites/${worksite.id}`)) {
          return jsonResponse(responsibilityDetail);
        }
        if (path.endsWith("/api/v1/worksites")) {
          return jsonResponse([worksite]);
        }
        throw new Error(`Ruta inesperada: ${path}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<HomePage />);
    await user.click(await screen.findByRole("button", { name: /obr-001/i }));
    await user.selectOptions(
      screen.getByLabelText(/actuar como/i),
      "responsable",
    );
    await user.click(
      await screen.findByRole("tab", { name: /responsables/i }),
    );
    await user.click(screen.getByRole("button", { name: "Cambiar auditor" }));

    expect(screen.getByLabelText("Persona auditora")).toBeVisible();
    expect(
      screen.queryByLabelText("Función en la obra"),
    ).not.toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Persona auditora"),
      "13000000-0000-0000-0000-000000000002",
    );
    await user.selectOptions(
      screen.getByLabelText(/Delegado por/),
      "11000000-0000-0000-0000-000000000002",
    );
    await user.click(screen.getByRole("button", { name: "Confirmar cambio" }));

    expect(await screen.findByText(/responsable cambiado/i)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/worksites/10000000-0000-4000-8000-000000000001/functional-assignments/11000000-0000-0000-0000-000000000001/change",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("crea, abre y navega una obra persistida", async () => {
    let created = false;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/api/v1/worksites") && init?.method === "POST") {
          created = true;
          expect(init.headers).toMatchObject({
            "X-Pilot-Actor": "responsable",
          });
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
    await user.selectOptions(
      await screen.findByLabelText(/actuar como/i),
      "responsable",
    );
    await screen.findByText(/creá o abrí una obra/i);
    await user.type(screen.getByLabelText("Código"), "OBR-001");
    await user.type(screen.getByLabelText("Nombre"), "Obra Piloto Norte");
    await user.type(screen.getByLabelText("País"), "Argentina");
    await user.type(screen.getByLabelText("Provincia"), "Provincia sintética");
    await user.type(screen.getByLabelText("Municipio"), "Municipio sintético");
    await user.click(screen.getByRole("button", { name: /crear y abrir/i }));

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inicio",
      }),
    ).toBeVisible();
    expect(screen.getByText(/obra creada y abierta/i)).toBeVisible();
    expect(screen.getByText("Próximas acciones")).toBeVisible();
    expect(screen.getByText("Alertas")).toBeVisible();
    expect(screen.queryByText("Acciones principales")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /contratistas/i }));
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
    expect(screen.getByText("Alertas")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /revisar documentos pendientes/i }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /revisar documentos pendientes/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /legajos técnicos/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 2, name: "Legajos Técnicos" }),
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
    await user.selectOptions(
      await screen.findByLabelText(/actuar como/i),
      "responsable",
    );
    await screen.findByText(/creá o abrí una obra/i);
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
      await screen.findByRole("tab", { name: /auditoría/i }),
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
    await user.click(await screen.findByRole("tab", { name: /etapas/i }));

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

  it("muestra la estructura del legajo aunque exista documentación previa", async () => {
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
          return jsonResponse({
            ...detail,
            contractors: [
              {
                id: "12000000-0000-0000-0000-000000000001",
                legal_name: "Contratista principal sintética",
                trade: "Construcción",
                participation_type: "PRINCIPAL",
              },
            ],
            documents: [
              {
                ...currentDocument,
                subject_kind: "CONTRACTOR",
                subject_id: "12000000-0000-0000-0000-000000000001",
              },
            ],
          });
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
      await screen.findByRole("tab", { name: /legajos técnicos/i }),
    );
    await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);

    expect(screen.getAllByText("Pendiente")[0]).toBeVisible();
    expect(
      screen.queryByLabelText("Título de la versión"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /registrar versión/i }),
    ).not.toBeInTheDocument();
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
      await screen.findByRole("tab", { name: /maquinarias/i }),
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
