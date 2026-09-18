/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0F172A',
        surface: {
          DEFAULT: '#1B2336',
          muted: '#151C2C',
          light: '#242F46',
          border: 'rgba(255, 255, 255, 0.08)',
        },
        telemetry: {
          cpu: '#06B6D4',      // Cyan
          memory: '#8B5CF6',   // Purple
          disk: '#F59E0B',     // Amber
          net: '#10B981',      // Emerald
          stall: '#F43F5E',    // Rose
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
        glow: '0 0 15px rgba(6, 182, 212, 0.35)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};
