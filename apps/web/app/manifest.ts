import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "H&S Gestión",
    short_name: "H&S",
    description: "Gestión trazable de Higiene y Seguridad en obras civiles.",
    start_url: "/",
    display: "standalone",
    background_color: "#f4f7f8",
    theme_color: "#10243b",
    lang: "es-AR",
  };
}
