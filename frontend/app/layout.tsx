import type { Metadata } from "next";
import Providers from "@/components/providers";
import "./globals.css";
import "@xyflow/react/dist/style.css";
export const metadata: Metadata = {
  title: "ContentForge AI · Ideas, backed by evidence",
  description:
    "A multi-agent content intelligence platform with live orchestration and evidence traceability.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
