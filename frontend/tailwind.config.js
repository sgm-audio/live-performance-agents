/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'app-bg': '#0a0a0a',
        'app-surface': '#1a1a1a',
        'app-border': '#2a2a2a',
        'app-primary': '#3b82f6',
        'app-success': '#10b981',
        'app-warning': '#f59e0b',
        'app-error': '#ef4444',
        'app-text': '#f3f4f6',
        'app-text-secondary': '#9ca3af',
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
