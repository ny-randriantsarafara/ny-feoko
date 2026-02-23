import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ambara — Transcript Editor",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#0a0a0a", color: "#e0e0e0", fontFamily: "system-ui" }}>
        {children}
      </body>
    </html>
  );
}
