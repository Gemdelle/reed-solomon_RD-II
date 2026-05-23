/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f4ff",
          100: "#dde6ff",
          500: "#4f6ef7",
          600: "#3b5af5",
          700: "#2a47e8",
          900: "#1a2f9e",
        },
      },
    },
  },
  plugins: [],
};
