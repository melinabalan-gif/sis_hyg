import { expect, test } from "@playwright/test";

test("synthetic create, reload, navigation and negative authorization journey", async ({
  page,
  request,
}, testInfo) => {
  const name = `SYNTHETIC-E2E-${testInfo.project.name}-${Date.now()}`;
  await page.goto("/");
  await expect(
    page.getByRole("status", { name: "Estado del entorno" }),
  ).toContainText("DATOS 100 % SINTÉTICOS");
  await page.getByLabel("Actuar como").selectOption("responsable");
  await page.getByLabel("Nombre de fantasía").fill(name);
  await page
    .getByLabel("Jurisdicción", { exact: true })
    .fill("Jurisdicción sintética");
  await page
    .getByLabel("Dirección", { exact: true })
    .fill("Calle sintética 100");
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/worksites") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Crear y abrir", exact: true })
    .click();
  const response = await created;
  expect(response.status()).toBe(201);
  const worksite = await response.json();
  expect(worksite.address).toBe("Calle sintética 100");
  await expect(
    page.getByRole("tablist", { name: "Módulos de la obra" }),
  ).toBeVisible();
  const firstTab = page.getByRole("tab").first();
  await firstTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab").nth(1)).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.reload();
  await page.getByLabel("Actuar como").selectOption("responsable");
  await page.getByRole("button").filter({ hasText: name }).click();
  await expect(
    page.getByRole("tablist", { name: "Módulos de la obra" }),
  ).toBeVisible();
  const detail = await request.get(`/api/v1/worksites/${worksite.id}`, {
    headers: { "X-Pilot-Actor": "responsable" },
  });
  expect(detail.status()).toBe(200);
  expect((await detail.json()).address).toBe("Calle sintética 100");
  const denied = await request.post("/api/v1/worksites", {
    headers: { "X-Pilot-Actor": "tecnico" },
    data: {
      name: "SYNTHETIC-DENIED",
      address: "Calle sintética 100",
      jurisdiction: "Sintética",
    },
  });
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe("pilot_worksite_create_required");
  expect((await request.get("/api/v1/worksites")).status()).toBe(401);
});
