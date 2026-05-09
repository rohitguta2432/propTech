import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["var(--font-poppins)", "Arial", "sans-serif"],
        body: ["var(--font-lora)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        // Anthropic brand
        ink: "#141413",
        cream: "#faf9f5",
        midgray: "#b0aea5",
        subtle: "#e8e6dc",
        orange: { DEFAULT: "#d97757", deep: "#c4623f" },
        ablue: "#6a9bcc",
        agreen: "#788c5d",
        // Traffic-light functional
        safe: "#10B981",
        amber: "#F59E0B",
        risky: "#EF4444",
      },
    },
  },
  plugins: [],
};

export default config;
