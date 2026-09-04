import { render, screen } from "@testing-library/react";

import HomePage from "../../app/page";
import { PROTOTYPE_NOTICE } from "../../src/components/environment-banner";

describe("HomePage", () => {
  it("identifica inequívocamente el entorno sintético", () => {
    render(<HomePage />);
    expect(screen.getByText(PROTOTYPE_NOTICE)).toBeVisible();
  });

  it("presenta landmarks, jerarquía y estados explícitos", () => {
    render(<HomePage />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /una base segura para gestionar/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByText("disponible", { selector: ".status-pill" }),
    ).toBeVisible();
    expect(screen.getByText("pendientes de configuración")).toBeVisible();
    expect(screen.getByText("no cargados")).toBeVisible();
  });

  it("no recrea el endpoint ni datos de obras del prototipo histórico", () => {
    const { container } = render(<HomePage />);
    expect(container.innerHTML).not.toContain("/obras");
    expect(screen.queryByText(/última auditoría/i)).not.toBeInTheDocument();
  });
});
