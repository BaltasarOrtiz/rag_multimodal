/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'cape-cod': {
          50: '#fafafa',
          100: '#f4f5f5',
          200: '#e4e6e7',
          300: '#d4d7d8',
          400: '#a0a8ab',
          500: '#70787b',
          600: '#51595c',
          700: '#393f41',
          800: '#27292a',
          900: '#181a1b',
          950: '#090b0b',
        },
      },
    },
  },
  plugins: [],
}
