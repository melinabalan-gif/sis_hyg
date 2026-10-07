import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomePage from "../../app/page";
import { documentMetadata } from "../../src/components/document-metadata-editor";
import type { PilotDocument } from "../../src/lib/pilot-api";

const site = {
  id: "10000000-0000-4000-8000-000000000001",
  code: "DEMO",
  name: "Obra sintética",
  address: "Calle sintética",
  jurisdiction: "Provincia sintética",
  status: "ACTIVE",
};
const principal = {
  id: "20000000-0000-4000-8000-000000000001",
  legal_name: "Principal sintética",
  trade: "Demo",
  participation_type: "PRINCIPAL",
};
const assignment = {
  id: "30000000-0000-4000-8000-000000000001",
  actor_id: "00000000-0000-4000-8000-000000000002",
  actor_key: "tecnico",
  actor_label: "Técnico",
  function_code: "TECNICO_HYS_CONTRATISTA_PRINCIPAL",
  represented_contractor_id: principal.id,
  valid_from: "2020-01-01",
  valid_to: null,
  permission_scope: "WORKSITE",
};
const baseDetail = {
  ...site,
  stages: [],
  contractors: [principal],
  people: [],
  functional_assignments: [assignment],
  documents: [],
  audits: [],
  machines: [],
  findings: [],
  metrics: {
    documents: {
      total: 0,
      by_status: {
        FALTANTE: 0,
        PENDIENTE: 0,
        OBSERVADO: 0,
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
      by_status: { OPERATIVA: 0, CON_OBSERVACIONES: 0, FUERA_DE_SERVICIO: 0 },
    },
    latest_audit: null,
    controls: {
      audit_id: null,
      numerator: 0,
      denominator: 0,
      ratio: null,
      excluded: { no_aplica: 0, no_verificado: 0 },
    },
    calculated_at: "2026-10-06T15:00:00Z",
  },
};
function response(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function installBackend(initial: unknown = baseDetail) {
  const detail = structuredClone(initial) as Omit<
    typeof baseDetail,
    "documents"
  > & { documents: Array<Record<string, unknown>> };
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const body = JSON.parse(String(init?.body ?? "{}"));
    if (init?.method === "POST" && path.endsWith("/documents")) {
      const item = {
        ...body,
        id: "40000000-0000-4000-8000-000000000001",
        version: 1,
        status: "PENDIENTE",
        review_status: "PENDIENTE",
        versions: [
          {
            ...body,
            id: "50000000-0000-4000-8000-000000000001",
            version_number: 1,
            actor_id: assignment.actor_id,
          },
        ],
        reviews: [],
      };
      detail.documents.push(item);
      return response(item, 201);
    }
    if (init?.method === "POST" && path.endsWith("/versions")) {
      const item = detail.documents.find((d) => path.includes(String(d.id)))!;
      Object.assign(item, body, {
        version: Number(item.version) + 1,
        status: "PENDIENTE",
        review_status: "PENDIENTE",
      });
      (item.versions as unknown[]).unshift({
        ...body,
        id: "50000000-0000-4000-8000-000000000002",
        version_number: item.version,
        actor_id: assignment.actor_id,
      });
      return response(item, 201);
    }
    if (path.endsWith(`/worksites/${site.id}`)) return response(detail);
    if (path.endsWith("/worksites")) return response([site]);
    throw new Error(`Unexpected synthetic route: ${path}`);
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, getDetail: () => detail };
}
async function openSite() {
  const user = userEvent.setup();
  render(<HomePage />);
  await user.click(await screen.findByRole("button", { name: /DEMO/i }));
  return user;
}
async function openPrincipal(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("tab", { name: "Legajos Técnicos" }));
  await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[0]);
}
afterEach(() => {
  vi.unstubAllGlobals();
});

it("AUD003 sends required jurisdiction with a typed worksite payload", async () => {
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      expect(JSON.parse(String(init.body))).toMatchObject({
        name: "Obra sintética",
        address: "Calle sintética",
        jurisdiction: "Provincia sintética",
      });
      return response(site, 201);
    }
    return response(
      String(input).endsWith(`/worksites/${site.id}`) ? baseDetail : [],
    );
  });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  render(<HomePage />);
  await user.selectOptions(
    await screen.findByLabelText("Actuar como"),
    "responsable",
  );
  await user.type(
    screen.getByLabelText("Nombre de fantasía"),
    "Obra sintética",
  );
  await user.type(screen.getByLabelText("Dirección"), "Calle sintética");
  await user.type(screen.getByLabelText("Jurisdicción"), "Provincia sintética");
  await user.click(screen.getByRole("button", { name: /crear y abrir/i }));
  await screen.findByText(/Obra creada y abierta/);
  await screen.findByRole("tablist", { name: "Módulos de la obra" });
});

it("AUD006 loads and versions document metadata and reopens persisted values", async () => {
  const backend = installBackend();
  const user = await openSite();
  await openPrincipal(user);
  const row = screen.getByText("Aviso de Obra", { exact: true }).closest("li")!;
  await user.click(within(row).getByRole("button", { name: "Cargar" }));
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Referencia sintética inicial",
  );
  await user.type(screen.getByLabelText("Vencimiento"), "2027-10-06");
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await screen.findByText(
    "Metadatos guardados y pendientes de revisión independiente.",
  );
  expect(backend.getDetail().documents[0]).toMatchObject({
    title: "Aviso de Obra",
    notes: "Referencia sintética inicial",
    subject_kind: "CONTRACTOR",
    subject_id: principal.id,
  });
  await user.click(
    within(
      screen.getByText("Aviso de Obra", { exact: true }).closest("li")!,
    ).getByRole("button", { name: "Actualizar" }),
  );
  await user.clear(screen.getByLabelText("Detalle del documento"));
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Referencia sintética actualizada",
  );
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await waitFor(() => expect(backend.getDetail().documents[0].version).toBe(2));
  await user.click(screen.getByRole("tab", { name: "Personal" }));
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByText("Aviso de Obra", { exact: true }).closest("li")!,
    ).getByRole("button", { name: "Actualizar" }),
  );
  expect(screen.getByLabelText("Detalle del documento")).toHaveValue(
    "Referencia sintética actualizada",
  );
});

it("AUD006 auxiliary availability survives a full component remount", async () => {
  const backend = installBackend();
  let user = await openSite();
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByRole("group", { name: "Baños: presencia o disponibilidad" }),
    ).getByRole("radio", { name: "Sí" }),
  );
  await waitFor(() =>
    expect(
      backend.fetch.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(true),
  );
  await waitFor(() => expect(backend.getDetail().documents).toHaveLength(1));
  expect(
    JSON.parse(String(backend.getDetail().documents[0].notes)),
  ).toMatchObject({ available: true });
  const { cleanup } = await import("@testing-library/react");
  cleanup();
  user = await openSite();
  await openPrincipal(user);
  expect(
    within(
      screen.getByRole("group", { name: "Baños: presencia o disponibilidad" }),
    ).getByRole("radio", { name: "Sí" }),
  ).toBeChecked();
});

it("AUD006 project program derives its assigned professional and persists weekly hours", async () => {
  const current = {
    ...assignment,
    actor_id: "00000000-0000-4000-8000-000000000003",
    actor_key: "responsable",
    function_code: "RESPONSABLE_HYS_PROYECTO",
    represented_contractor_id: null,
  };
  const auditor = {
    ...assignment,
    id: "30000000-0000-4000-8000-000000000002",
    actor_id: "00000000-0000-4000-8000-000000000001",
    actor_key: "auditor",
    function_code: "AUDITOR",
    person_name: "Auditora sintética",
    profession_code: "TECNICO_HYS",
  };
  const backend = installBackend({
    ...baseDetail,
    functional_assignments: [current, auditor],
  });
  const user = await openSite();
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await user.click(screen.getByRole("tab", { name: "Legajos Técnicos" }));
  await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[1]);
  expect(screen.getByLabelText("Auditor asignado")).toHaveValue(
    "Auditora sintética",
  );
  expect(screen.getByLabelText("Profesión del auditor")).toHaveValue(
    "Técnico H&S",
  );
  const card = screen
    .getByRole("heading", { name: "Programa de Seguridad de Proyecto" })
    .closest("article")!;
  await user.click(within(card).getByRole("button", { name: "Completar" }));
  await user.type(
    screen.getByLabelText("Carga horaria semanal del auditor"),
    "12",
  );
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Programa sintético",
  );
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await waitFor(() => expect(backend.getDetail().documents).toHaveLength(1));
  expect(
    JSON.parse(String(backend.getDetail().documents[0].notes)),
  ).toMatchObject({ weekly_hours: 12, auditor_assignment_id: auditor.id });
  await user.click(screen.getByRole("tab", { name: "Personal" }));
  await user.click(screen.getByRole("tab", { name: "Legajos Técnicos" }));
  await user.click(screen.getAllByRole("button", { name: "Ver legajo" })[1]);
  expect(
    screen.getByLabelText("Carga horaria semanal del auditor"),
  ).toHaveValue(12);
});
it("AUD007 counts every unresolved document and finding without claiming a pending file is current", async () => {
  const doc = {
    id: "doc-pending",
    subject_kind: "CONTRACTOR",
    subject_id: principal.id,
    title: "Aviso de Obra",
    document_type: "LEGAJO_TECNICO",
    status: "PENDIENTE",
    version: 1,
    versions: [],
    reviews: [],
  };
  installBackend({
    ...baseDetail,
    documents: [doc],
    metrics: {
      ...baseDetail.metrics,
      documents: {
        total: 3,
        by_status: {
          ...baseDetail.metrics.documents.by_status,
          PENDIENTE: 1,
          OBSERVADO: 1,
          VIGENTE: 1,
        },
      },
      findings: {
        total: 2,
        by_status: {
          ...baseDetail.metrics.findings.by_status,
          EN_CORRECCION: 2,
        },
        overdue: 0,
      },
    },
  });
  const user = await openSite();
  expect(screen.getByText("2 requieren atención")).toBeInTheDocument();
  expect(screen.getByText("2 abiertos o por verificar")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Legajos Técnicos" }));
  expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
  expect(screen.queryByText("Documentación vigente")).not.toBeInTheDocument();
});

it("AUD008 supports roving keyboard tabs with Home and End", async () => {
  installBackend();
  const user = await openSite();
  const start = screen.getByRole("tab", { name: "Inicio" });
  start.focus();
  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("tab", { name: "Responsables" })).toHaveFocus();
  expect(start).toHaveAttribute("tabindex", "-1");
  await user.keyboard("{End}");
  expect(screen.getByRole("tab", { name: "Seguimiento" })).toHaveFocus();
  await user.keyboard("{Home}");
  expect(start).toHaveFocus();
});

it("AUD008 names inline stage and person verification controls", async () => {
  installBackend({
    ...baseDetail,
    functional_assignments: [
      assignment,
      {
        ...assignment,
        actor_id: "00000000-0000-4000-8000-000000000003",
        actor_key: "responsable",
        function_code: "RESPONSABLE_HYS_PROYECTO",
        represented_contractor_id: null,
      },
    ],
    stages: [{ id: "stage", name: "Preparación", status: "ACTIVA" }],
    people: [
      {
        id: "person",
        full_name: "Persona sintética",
        contractor_id: principal.id,
      },
    ],
  });
  const user = await openSite();
  await user.click(screen.getByRole("tab", { name: "Etapas" }));
  await user.click(screen.getByText("Actualizar etapa"));
  expect(
    screen.getByRole("combobox", { name: "Estado de etapa" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Fin de etapa")).toBeInTheDocument();
  expect(
    screen.getByRole("textbox", { name: "Nota del cambio" }),
  ).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await screen.findByRole("tab", { name: "Personal" });
  await user.click(screen.getByRole("tab", { name: "Personal" }));
  expect(
    screen.getByRole("combobox", { name: "Resultado de habilitación" }),
  ).toBeInTheDocument();
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
it("AUD009 ignores an obsolete actor response and only loads selected details once", async () => {
  const old = deferred<Response>();
  let initial = true;
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const headers = init?.headers as Record<string, string>;
    if (
      String(input).endsWith("/worksites") &&
      headers["X-Pilot-Actor"] === "tecnico" &&
      initial
    ) {
      initial = false;
      return old.promise;
    }
    return Promise.resolve(
      response(
        String(input).endsWith(`/worksites/${site.id}`) ? baseDetail : [site],
      ),
    );
  });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  render(<HomePage />);
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await user.click(await screen.findByRole("button", { name: /DEMO/ }));
  await screen.findByRole("tab", { name: "Inicio" });
  await act(async () => {
    old.resolve(response([{ ...site, id: "obsolete", code: "OBSOLETO" }]));
  });
  expect(
    screen.queryByRole("button", { name: /OBSOLETO/ }),
  ).not.toBeInTheDocument();
  expect(
    fetch.mock.calls.filter(([url]) =>
      String(url).endsWith(`/worksites/${site.id}`),
    ),
  ).toHaveLength(1);
});

it.each(["expired", "future", "absent"])(
  "AUD010 prevents resource mutation with %s assignments",
  async (kind) => {
    installBackend({
      ...baseDetail,
      functional_assignments:
        kind === "absent"
          ? []
          : [
              {
                ...assignment,
                valid_from: kind === "future" ? "2999-01-01" : "2020-01-01",
                valid_to: kind === "expired" ? "2020-02-01" : null,
              },
            ],
    });
    const user = await openSite();
    await user.click(screen.getByRole("tab", { name: "Etapas" }));
    expect(
      screen.getByRole("button", { name: "Guardar etapa" }),
    ).toBeDisabled();
    await openPrincipal(user);
    const row = screen
      .getByText("Aviso de Obra", { exact: true })
      .closest("li")!;
    expect(
      within(row).queryByRole("button", { name: "Cargar" }),
    ).not.toBeInTheDocument();
  },
);

it("AUD009 ignores reversed worksite detail responses", async () => {
  const old = deferred<Response>();
  const second = {
    ...site,
    id: "10000000-0000-4000-8000-000000000002",
    code: "SECOND",
    name: "Segunda obra sintética",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      return path.endsWith(`/worksites/${site.id}`)
        ? old.promise
        : Promise.resolve(
            response(
              path.endsWith(`/worksites/${second.id}`)
                ? { ...baseDetail, ...second }
                : [site, second],
            ),
          );
    }),
  );
  const user = userEvent.setup();
  render(<HomePage />);
  await user.click(await screen.findByRole("button", { name: /DEMO/ }));
  await user.click(screen.getByRole("button", { name: "Obras" }));
  await user.click(await screen.findByRole("button", { name: /SECOND/ }));
  await screen.findByRole("tab", { name: "Inicio" });
  await act(async () => old.resolve(response(baseDetail)));
  expect(
    screen.getByText("Segunda obra sintética", { exact: true }),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Obra sintética", { exact: true }),
  ).not.toBeInTheDocument();
});
it("AUD009 never refreshes or announces an obsolete mutation after switching actors", async () => {
  const saving = deferred<Response>();
  const backend = installBackend();
  const real = backend.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "POST" ? saving.promise : real(input, init),
    ),
  );
  const user = await openSite();
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByText("Aviso de Obra", { exact: true }).closest("li")!,
    ).getByRole("button", { name: "Cargar" }),
  );
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Operación sintética",
  );
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await user.selectOptions(screen.getByLabelText("Actuar como"), "auditor");
  await screen.findByRole("tab", { name: "Inicio" });
  const calls = real.mock.calls.length;
  await act(async () => saving.resolve(response({}, 201)));
  expect(real.mock.calls).toHaveLength(calls);
  expect(screen.queryByText(/Metadatos guardados/)).not.toBeInTheDocument();
});

it("AUD007 does not mark a partly populated technical file complete", async () => {
  installBackend({
    ...baseDetail,
    documents: [
      {
        id: "doc",
        subject_kind: "CONTRACTOR",
        subject_id: principal.id,
        title: "Aviso de Obra",
        status: "VIGENTE",
        versions: [],
        reviews: [],
        version: 1,
      },
    ],
  });
  const user = await openSite();
  await user.click(screen.getByRole("tab", { name: "Legajos Técnicos" }));
  expect(screen.getByText("Documentación incompleta")).toBeInTheDocument();
  expect(screen.queryByText("Documentación vigente")).not.toBeInTheDocument();
});

it.each(["ORGANIZATION", "unknown-function", "archived"])(
  "AUD010 does not expose technical file mutation for %s",
  async (kind) => {
    installBackend({
      ...baseDetail,
      status: kind === "archived" ? "ARCHIVED" : "ACTIVE",
      functional_assignments: [
        {
          ...assignment,
          permission_scope: kind === "ORGANIZATION" ? kind : "WORKSITE",
          function_code:
            kind === "unknown-function" ? "UNKNOWN" : assignment.function_code,
        },
      ],
    });
    const user = await openSite();
    await openPrincipal(user);
    expect(screen.queryAllByRole("button", { name: "Cargar" })).toHaveLength(0);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  },
);

const auditorAssignment = {
  ...assignment,
  actor_id: "00000000-0000-4000-8000-000000000001",
  actor_key: "auditor",
  function_code: "AUDITOR",
  represented_contractor_id: null,
};
const audit = {
  id: "audit-current",
  status: "EN_CURSO",
  author_id: "00000000-0000-4000-8000-000000000003",
  editor_id: auditorAssignment.actor_id,
  auditor_actor_id: auditorAssignment.actor_id,
  auditor_assignment_id: auditorAssignment.id,
  started_at: "2026-10-06T15:00:00Z",
  available_controls: [
    { catalog_code: "SYN", catalog_title: "Control sintético" },
  ],
  controls: [],
};
it.each([true, false])(
  "AUD010 follows current audit editor rather than original author: %s",
  async (isEditor) => {
    installBackend({
      ...baseDetail,
      functional_assignments: [auditorAssignment],
      audits: [
        {
          ...audit,
          editor_id: isEditor
            ? auditorAssignment.actor_id
            : assignment.actor_id,
        },
      ],
    });
    const user = await openSite();
    await user.selectOptions(screen.getByLabelText("Actuar como"), "auditor");
    await screen.findByRole("tab", { name: "Auditoría" });
    await user.click(screen.getByRole("tab", { name: "Auditoría" }));
    const button = screen.getByRole("button", { name: "Registrar control" });
    if (isEditor) expect(button).toBeEnabled();
    else expect(button).toBeDisabled();
  },
);

it("AUD010 can start a new audit after someone else's finalized audit", async () => {
  installBackend({
    ...baseDetail,
    functional_assignments: [auditorAssignment],
    audits: [
      {
        ...audit,
        status: "FINALIZADA",
        editor_id: assignment.actor_id,
      },
    ],
  });
  const user = await openSite();
  await user.selectOptions(screen.getByLabelText("Actuar como"), "auditor");
  await screen.findByRole("tab", { name: "Auditoría" });
  await user.click(screen.getByRole("tab", { name: "Auditoría" }));
  expect(
    screen.getByRole("button", { name: "Iniciar auditoría" }),
  ).toBeEnabled();
});

it("AUD010 allows an assigned auditor to correct but never verify a finding", async () => {
  installBackend({
    ...baseDetail,
    functional_assignments: [auditorAssignment],
    findings: [
      {
        id: "finding",
        audit_id: audit.id,
        title: "Desvío sintético",
        description: "Corregir",
        status: "ABIERTO",
        severity_code: "MEDIA",
        due_at: "2027-01-01T15:00:00Z",
        created_by: assignment.actor_id,
        corrections: [],
        verifications: [],
        events: [],
      },
    ],
  });
  const user = await openSite();
  await user.selectOptions(screen.getByLabelText("Actuar como"), "auditor");
  await screen.findByRole("tab", { name: "Seguimiento" });
  await user.click(screen.getByRole("tab", { name: "Seguimiento" }));
  expect(
    screen.getByRole("button", { name: "Agregar corrección" }),
  ).toBeEnabled();
  expect(
    screen.queryByRole("button", { name: "Registrar verificación" }),
  ).not.toBeInTheDocument();
});

it("AUD006 preserves unknown metadata and human notes on auxiliary updates", async () => {
  const backend = installBackend({
    ...baseDetail,
    documents: [
      {
        id: "aux",
        title: "Baños",
        document_type: "SERVICIO_AUXILIAR",
        subject_kind: "CONTRACTOR",
        subject_id: principal.id,
        version: 1,
        status: "PENDIENTE",
        versions: [],
        reviews: [],
        notes: JSON.stringify({
          schema: "hys.technical_metadata.v1",
          detail: "Nota humana",
          available: false,
          extension: { preserved: true },
        }),
        valid_from: "2020-01-01",
        expires_on: "2027-01-01",
      },
    ],
  });
  const user = await openSite();
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByRole("group", { name: "Baños: presencia o disponibilidad" }),
    ).getByRole("radio", { name: "Sí" }),
  );
  await waitFor(() => expect(backend.getDetail().documents[0].version).toBe(2));
  const stored = backend.getDetail().documents[0];
  expect(JSON.parse(String(stored.notes))).toMatchObject({
    detail: "Nota humana",
    extension: { preserved: true },
    available: true,
  });
  expect(stored.valid_from).toBe("2020-01-01");
  expect(stored.expires_on).toBe("2027-01-01");
  const mutation = backend.fetch.mock.calls.find(
    ([, init]) => init?.method === "POST",
  )![1]!;
  expect(JSON.parse(String(mutation.body))).toMatchObject({
    valid_from: "2020-01-01",
    expires_on: "2027-01-01",
  });
});

it("AUD006 treats legacy notes as human text and rejects fractional invalid hours", () => {
  expect(
    documentMetadata({ notes: "Legacy synthetic note" } as PilotDocument),
  ).toEqual({ detail: "Legacy synthetic note" });
  expect(
    documentMetadata({
      notes: JSON.stringify({
        schema: "hys.technical_metadata.v1",
        detail: "Human",
        weekly_hours: 1.25,
      }),
    } as PilotDocument).weekly_hours,
  ).toBeUndefined();
});

it("AUD009 discards a mutation refresh that resolves after an actor change", async () => {
  const staleDetail = deferred<Response>();
  const backend = installBackend();
  let mutationFinished = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const headers = init?.headers as Record<string, string>;
      if (init?.method === "POST") {
        const result = await backend.fetch(input, init);
        mutationFinished = true;
        return result;
      }
      if (
        mutationFinished &&
        headers["X-Pilot-Actor"] === "tecnico" &&
        String(input).endsWith(`/worksites/${site.id}`)
      )
        return staleDetail.promise;
      return backend.fetch(input, init);
    }),
  );
  const user = await openSite();
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByText("Aviso de Obra", { exact: true }).closest("li")!,
    ).getByRole("button", { name: "Cargar" }),
  );
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Cambio sintético",
  );
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await waitFor(() => expect(mutationFinished).toBe(true));
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await screen.findByRole("tab", { name: "Inicio" });
  const calls = backend.fetch.mock.calls.length;
  await act(async () =>
    staleDetail.resolve(
      response({ ...baseDetail, name: "RESPUESTA OBSOLETA" }),
    ),
  );
  expect(screen.queryByText("RESPUESTA OBSOLETA")).not.toBeInTheDocument();
  expect(screen.queryByText(/Metadatos guardados/)).not.toBeInTheDocument();
  expect(backend.fetch.mock.calls).toHaveLength(calls);
});

it("AUD009 preserves a confirmed creation when the next list replays the pre-creation snapshot", async () => {
  const creation = deferred<Response>();
  const replay = deferred<Response>();
  const created = {
    ...site,
    id: "10000000-0000-4000-8000-000000000009",
    code: "NEW",
    name: "Nueva obra sintética",
  };
  let posted = false;
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (init?.method === "POST") {
      posted = true;
      return creation.promise;
    }
    if (path.endsWith(`/worksites/${created.id}`))
      return Promise.resolve(response({ ...baseDetail, ...created }));
    return posted
      ? replay.promise.then((value) => value.clone())
      : Promise.resolve(response([site]));
  });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  render(<HomePage />);
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await user.type(screen.getByLabelText("Nombre de fantasía"), created.name);
  await user.type(screen.getByLabelText("Dirección"), created.address);
  await user.type(screen.getByLabelText("Jurisdicción"), created.jurisdiction);
  await user.click(screen.getByRole("button", { name: /crear y abrir/i }));
  await act(async () => creation.resolve(response(created, 201)));
  await act(async () => replay.resolve(response([site])));
  await screen.findByRole("tablist", { name: "Módulos de la obra" });
  expect(screen.getByText(created.name, { exact: true })).toBeInTheDocument();
  expect(
    fetch.mock.calls.filter(([input]) =>
      String(input).endsWith(`/worksites/${created.id}`),
    ),
  ).toHaveLength(1);
});

it.each([403, 404])(
  "AUD009 authoritative detail denial %s clears selection and creation success",
  async (status) => {
    let created = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          created = true;
          return Promise.resolve(response(site, 201));
        }
        return Promise.resolve(
          response(
            String(input).endsWith(`/worksites/${site.id}`)
              ? { detail: "Obra no visible" }
              : created
                ? [site]
                : [],
            String(input).endsWith(`/worksites/${site.id}`) ? status : 200,
          ),
        );
      }),
    );
    const user = userEvent.setup();
    render(<HomePage />);
    await user.selectOptions(
      screen.getByLabelText("Actuar como"),
      "responsable",
    );
    await user.type(screen.getByLabelText("Nombre de fantasía"), site.name);
    await user.type(screen.getByLabelText("Dirección"), site.address);
    await user.type(screen.getByLabelText("Jurisdicción"), site.jurisdiction);
    await user.click(screen.getByRole("button", { name: /crear y abrir/i }));
    await screen.findByText("Obra no visible");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByText(/Obra creada y abierta/)).not.toBeInTheDocument();
  },
);

it("AUD009 in-flight creation cannot publish or select for a different actor", async () => {
  const creation = deferred<Response>();
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "POST" ? creation.promise : Promise.resolve(response([])),
  );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  render(<HomePage />);
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await user.type(screen.getByLabelText("Nombre de fantasía"), site.name);
  await user.type(screen.getByLabelText("Dirección"), site.address);
  await user.type(screen.getByLabelText("Jurisdicción"), site.jurisdiction);
  await user.click(screen.getByRole("button", { name: /crear y abrir/i }));
  await user.selectOptions(screen.getByLabelText("Actuar como"), "auditor");
  await act(async () => creation.resolve(response(site, 201)));
  expect(screen.queryByText(/Obra creada y abierta/)).not.toBeInTheDocument();
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(
    fetch.mock.calls.some(([input]) =>
      String(input).endsWith(`/worksites/${site.id}`),
    ),
  ).toBe(false);
});

it("AUD009 resolves expired visibility through detail even when the new actor list omits selection", async () => {
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const denied =
      (init?.headers as Record<string, string>)["X-Pilot-Actor"] ===
      "responsable";
    const detail = String(input).endsWith(`/worksites/${site.id}`);
    return Promise.resolve(
      response(
        detail
          ? denied
            ? { detail: "Asignación vencida o fuera de alcance" }
            : baseDetail
          : denied
            ? []
            : [site],
        detail && denied ? 404 : 200,
      ),
    );
  });
  vi.stubGlobal("fetch", fetch);
  const user = await openSite();
  await screen.findByRole("tab", { name: "Inicio" });
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await screen.findByText("Asignación vencida o fuera de alcance");
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(
    screen.queryByText(site.name, { exact: true }),
  ).not.toBeInTheDocument();
  expect(
    fetch.mock.calls.some(
      ([input, init]) =>
        String(input).endsWith(`/worksites/${site.id}`) &&
        (init?.headers as Record<string, string>)["X-Pilot-Actor"] ===
          "responsable",
    ),
  ).toBe(true);
});

it("AUD009 does not mistake a temporary detail error for authoritative absence", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const selected = String(input).endsWith(`/worksites/${site.id}`);
      const recovery =
        (init?.headers as Record<string, string>)["X-Pilot-Actor"] ===
        "responsable";
      return Promise.resolve(
        response(
          selected
            ? recovery
              ? baseDetail
              : { detail: "Servicio temporalmente no disponible" }
            : recovery
              ? []
              : [site],
          selected && !recovery ? 503 : 200,
        ),
      );
    }),
  );
  const user = await openSite();
  await screen.findByText("Servicio temporalmente no disponible");
  await user.selectOptions(screen.getByLabelText("Actuar como"), "responsable");
  await screen.findByRole("tablist", { name: "Módulos de la obra" });
  expect(screen.getByText(site.name, { exact: true })).toBeInTheDocument();
});

it("AUD009 mutation refresh denial clears previously visible detail without a success announcement", async () => {
  const backend = installBackend();
  let posted = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        const result = await backend.fetch(input, init);
        posted = true;
        return result;
      }
      if (posted && String(input).endsWith(`/worksites/${site.id}`))
        return response({ detail: "Alcance revocado" }, 403);
      if (posted && String(input).endsWith("/worksites")) return response([]);
      return backend.fetch(input, init);
    }),
  );
  const user = await openSite();
  await openPrincipal(user);
  await user.click(
    within(
      screen.getByText("Aviso de Obra", { exact: true }).closest("li")!,
    ).getByRole("button", { name: "Cargar" }),
  );
  await user.type(
    screen.getByLabelText("Detalle del documento"),
    "Referencia sintética",
  );
  await user.click(screen.getByRole("button", { name: "Guardar metadatos" }));
  await screen.findByText("Alcance revocado");
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(
    screen.queryByText(site.name, { exact: true }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText(/Metadatos guardados/)).not.toBeInTheDocument();
});
