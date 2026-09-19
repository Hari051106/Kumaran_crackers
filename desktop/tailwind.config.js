/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Kumaran Crackers brand: a warm festive amber against a deep slate
        // shell - celebratory without being garish on a screen someone stares
        // at all day.
        brand: {
          50: '#fff8ed',
          100: '#ffefd4',
          200: '#ffdba8',
          300: '#ffc071',
          400: '#ff9d38',
          500: '#fe8112',
          600: '#ef6608',
          700: '#c64d09',
          800: '#9d3d10',
          900: '#7e3310',
        },
        shell: {
          50: '#f6f7f9',
          100: '#eceef2',
          200: '#d5d9e2',
          300: '#b0b8c9',
          400: '#8591ab',
          500: '#667391',
          600: '#515c78',
          700: '#424a61',
          800: '#3a4052',
          900: '#141a27',
          950: '#0c111b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(16 24 40 / 0.06), 0 1px 3px 0 rgb(16 24 40 / 0.10)',
        panel: '0 4px 6px -1px rgb(16 24 40 / 0.08), 0 2px 4px -2px rgb(16 24 40 / 0.06)',
      },
    },
  },
  plugins: [],
};
