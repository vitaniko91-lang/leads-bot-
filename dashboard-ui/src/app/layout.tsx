import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Leads Bot Dashboard",
  description: "Internal control panel for the freelance leads bot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://rsms.me/" />
        <link rel="stylesheet" href="https://rsms.me/inter/inter.css" />
      </head>
      <body className="min-h-screen bg-bg text-text">{children}</body>
    </html>
  );
}
