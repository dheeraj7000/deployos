import "./globals.css";
import React from "react";

export const metadata = {
  title: "DeployOS — Reliability, Execution & Evaluation Platform for Production AI Agents",
  description: "Production infrastructure for durable agent workflows and deterministic execution policies.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0b0f19] text-slate-100 antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
