import { expect, test } from "@playwright/test";

test("confirmed creation survives replay of the actual pre-creation list", async ({
  page,
  request,
}, testInfo) => {
  const previous = await request.get("/api/v1/worksites", {
    headers: { "X-Pilot-Actor": "responsable" },
  });
  expect(previous.status()).toBe(200);
  const snapshot: unknown = await previous.json();
  let confirmed = false;
  let replayed = false;
  page.on("response", (response) => {
    if (
      response.url().endsWith("/api/v1/worksites") &&
      response.request().method() === "POST" &&
      response.status() === 201
    )
      confirmed = true;
  });
  await page.route("**/api/v1/worksites", async (route) => {
    if (confirmed && !replayed && route.request().method() === "GET") {
      replayed = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(snapshot),
      });
    } else await route.continue();
  });
  await page.goto("/");
  await page.getByLabel("Actuar como").selectOption("responsable");
  const name = `SYNTHETIC-SNAPSHOT-${testInfo.project.name}-${Date.now()}`;
  await page.getByLabel("Nombre de fantasía").fill(name);
  await page
    .getByLabel("Dirección", { exact: true })
    .fill("Calle sintética 100");
  await page
    .getByLabel("Jurisdicción", { exact: true })
    .fill("Jurisdicción sintética");
  const creation = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/worksites") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Crear y abrir", exact: true })
    .click();
  const response = await creation;
  expect(response.status()).toBe(201);
  const created = await response.json();
  expect(created.name).toBe(name);
  await expect(
    page.getByRole("tablist", { name: "Módulos de la obra" }),
  ).toBeVisible();
  await expect.poll(() => replayed).toBe(true);
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  const detail = await request.get(`/api/v1/worksites/${created.id}`, {
    headers: { "X-Pilot-Actor": "responsable" },
  });
  expect(detail.status()).toBe(200);
  expect((await detail.json()).address).toBe("Calle sintética 100");
});
