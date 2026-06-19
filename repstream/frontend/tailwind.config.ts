import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0f172a',
          800: '#1e293b',
          700: '#334155',
        },
        priority: {
          high: '#f97316',       // orange-500
          medium: '#3b82f6',     // blue-500
          low: '#94a3b8',        // slate-400
        },
        badge: {
          insight: '#7c3aed',    // purple-600
          matched: '#0d9488',    // teal-600
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
