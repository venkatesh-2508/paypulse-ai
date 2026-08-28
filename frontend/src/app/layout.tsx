import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "PayPulse AI | Payment Incident Intelligence",
  description: "Understand every payment incident. Act before revenue is lost.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-container">
          <Navigation />
          <div className="main-content">
            <Header />
            <main className="page-body">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
