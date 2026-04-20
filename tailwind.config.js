/** @type {import('tailwindcss').Config} */
module.exports = {
  prefix: "tw-",
  content: [
    "./src/templates/**/*.html.jinja",
    "./src/static/js/**/*.js",
    "./src/routes/**/*.py",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0d1117",
          secondary: "#161b22",
          tertiary: "#21262d",
          card: "#1c2128",
        },
        border: { DEFAULT: "#30363d" },
        text: {
          primary: "#e6edf3",
          secondary: "#8b949e",
          muted: "#6e7681",
        },
        accent: { DEFAULT: "#58a6ff", hover: "#79c0ff" },
        band: {
          u: "#56B4E9",
          g: "#009E73",
          r: "#D55E00",
          i: "#E69F00",
          z: "#CC79A7",
          y: "#0072B2",
        },
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "ui-sans-serif", "system-ui"],
        mono: ["'IBM Plex Mono'", "ui-monospace"],
      },
    },
  },
  plugins: [],
};
