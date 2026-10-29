/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0e11",
        panel: "#131722",
        line: "#2a2e39",
        mist: "#787b86",
        foam: "#d1d4dc",
        tide: "#2962ff",
        ember: "#e6b450",
        signal: "#f23645",
      },
    },
  },
  plugins: [],
};
