/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Terminal theme colors
        terminal: {
          bg: '#0c0c0c',
          text: '#00ff41',
          amber: '#ffb000',
          red: '#ff6b6b',
          blue: '#74c0fc',
          gray: '#6c757d'
        },
        // LCARS theme colors
        lcars: {
          orange: '#ff9f00',
          blue: '#5555ff',
          red: '#cc6666',
          purple: '#c9c',
          yellow: '#ffff99',
          bg: '#000000',
          panel: '#333366'
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Monaco', 'Consolas', 'monospace'],
        lcars: ['Antonio', 'Helvetica Neue', 'Arial', 'sans-serif']
      },
      animation: {
        'terminal-blink': 'blink 1s step-start infinite',
        'lcars-pulse': 'pulse 2s ease-in-out infinite alternate',
        'typing': 'typing 0.5s steps(1, end)',
        'scan-line': 'scan-line 2s linear infinite'
      },
      keyframes: {
        blink: {
          '0%, 50%': { opacity: '1' },
          '51%, 100%': { opacity: '0' }
        },
        typing: {
          from: { width: '0' },
          to: { width: '100%' }
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100vh)' },
          '100%': { transform: 'translateY(100vh)' }
        }
      },
      borderRadius: {
        'lcars': '0 20px 20px 0',
        'lcars-left': '20px 0 0 20px',
        'lcars-pill': '50px'
      }
    },
  },
  plugins: [],
  darkMode: 'class'
}