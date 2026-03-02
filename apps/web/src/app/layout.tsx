import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ambara — Transcript Editor",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="m-0">
        {children}
      </body>
    </html>
  );
}
