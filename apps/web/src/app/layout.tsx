import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TaxRAG",
  description: "Source-grounded answers about Brazilian individual income tax.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
