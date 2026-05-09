import type { Metadata } from "next";
import { Poppins, Lora, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-poppins",
  display: "swap",
});
const lora = Lora({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-lora",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PropCheck — AI-powered property trust score for India",
  description:
    "AI-powered trust verification for any Magicbricks, 99acres, Housing or NoBroker listing in 30 seconds. Free, neutral, built for Indian buyers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${poppins.variable} ${lora.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
