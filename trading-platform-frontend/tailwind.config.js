/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#000000',
          card: '#0a0a0a',
          border: '#1a1a1a',
          text: '#9ca3af',
          hover: '#1f1f1f',
        }
      }
    },
  },
  plugins: [],
};
