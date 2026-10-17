import {LocalPerformanceProbe} from '@/components/LocalPerformanceProbe';
import type { Metadata } from "next";
import "./globals.css";
import { AuthBootstrap } from "@/components/auth/AuthBootstrap";
import { APP_NAME, APP_TAGLINE, APP_DESCRIPTION } from "@/config/brand";

export const metadata: Metadata = {
  title: `${APP_NAME} — ${APP_TAGLINE}`,
  description: APP_DESCRIPTION,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthBootstrap><LocalPerformanceProbe/>{children}</AuthBootstrap>
      </body>
    </html>
  );
}
