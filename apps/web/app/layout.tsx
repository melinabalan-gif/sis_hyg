import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

const publicOrigin = new URL(
  process.env.HYS_PUBLIC_ORIGIN ?? "https://localhost",
);

export const metadata: Metadata = {
  metadataBase: publicOrigin,
  title: "H&S Gestión · Prototipo sintético",
  description:
    "Base segura y trazable para la gestión de Higiene y Seguridad en obras civiles.",
  openGraph: {
    type: "website",
    locale: "es_AR",
    title: "H&S Gestión",
    description: "Una base segura para gestionar H&S",
    images: [
      {
        url: "/og.png",
        width: 1730,
        height: 909,
        alt: "H&S Gestión · Una base segura para gestionar H&S",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "H&S Gestión",
    description: "Una base segura para gestionar H&S",
    images: ["/og.png"],
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#10243b",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
