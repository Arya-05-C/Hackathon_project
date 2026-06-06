import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";
import Sidebar from "../components/Sidebar";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: "ProcureIntel | AI Procurement Decision Hub",
  description: "AI-powered procurement risks dashboard, deterministic supplier recommendations, and explanatory Copilot advisor.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} antialiased text-[#F3F4F6] bg-[#080C14] min-h-screen`}>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 h-screen overflow-y-auto relative bg-[#080C14]">
            {/* Ambient Background Radial Glows */}
            <div className="absolute top-[-200px] left-[200px] w-[500px] h-[500px] rounded-full bg-indigo-600/10 blur-[130px] pointer-events-none" />
            <div className="absolute bottom-[-100px] right-[100px] w-[400px] h-[400px] rounded-full bg-blue-600/5 blur-[120px] pointer-events-none" />
            
            <div className="p-8 max-w-[1400px] mx-auto w-full relative z-10">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
