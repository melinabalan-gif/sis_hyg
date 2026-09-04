import { GET } from "../../app/healthz/route";

describe("GET /healthz", () => {
  it("responde sin consultar dependencias y evita cache", async () => {
    const response = GET();
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    await expect(response.json()).resolves.toEqual({
      status: "ok",
      service: "web",
    });
  });
});
