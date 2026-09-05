// v1.0 | 04-Sep-2026 | Define the simulator application shell.

import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "KaKi-Talkie Simulator",
  description: "Browser contract twin for the KaKi-Talkie device",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
