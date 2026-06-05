/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["system-ui", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Onomber", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["0.8125rem", { lineHeight: "1.25rem" }],
        sm: ["0.9375rem", { lineHeight: "1.375rem" }],
        base: ["1.0625rem", { lineHeight: "1.625rem" }],
        lg: ["1.25rem", { lineHeight: "1.75rem" }],
        xl: ["1.5rem", { lineHeight: "2rem" }],
        "2xl": ["1.75rem", { lineHeight: "2.125rem" }],
        "3xl": ["2.125rem", { lineHeight: "2.375rem" }],
        "4xl": ["2.625rem", { lineHeight: "2.75rem" }],
        "5xl": ["3.5rem", { lineHeight: "1.1" }],
        "6xl": ["4.25rem", { lineHeight: "1.05" }],
      },
      colors: {
        brand: {
          50: "#f0f4ff",
          100: "#dde6ff",
          500: "#4f6ef7",
          600: "#3b5af5",
          700: "#2a47e8",
          900: "#1a2f9e",
        },
        bird: {
          magenta: "#e879f9",
          cyan: "#22d3ee",
          violet: "#a78bfa",
        },
      },
    },
  },
  plugins: [],
};
