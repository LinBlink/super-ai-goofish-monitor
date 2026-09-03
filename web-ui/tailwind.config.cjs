const animate = require("tailwindcss-animate")

module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx,vue}',
    './components/**/*.{ts,tsx,vue}',
    './app/**/*.{ts,tsx,vue}',
    './src/**/*.{ts,tsx,vue}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // HSL slots kept for shadcn primitives that reference them
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        // Goofish palette (utility helpers)
        brand: {
          yellow: "#ffe60f",
          "yellow-hover": "#ffef68",
          op: "#3178f6",
          "op-hover": "#2566dc",
          price: "#ff4f24",
          highlight: "#f58300",
          danger: "#ff3141",
          success: "#14c38e",
          page: "#f5f7f9",
          line: "#ececec",
          placeholder: "#eaeaea",
          ink: "#1f1f1f",
          muted: "#666666",
          subtle: "#999999",
        },
      },
      boxShadow: {
        xy: "0 4px 14px 0 rgba(0, 0, 0, 0.06)",
        "xy-hover": "0 8px 24px 0 rgba(0, 0, 0, 0.10)",
      },
      borderRadius: {
        lg: "20px",
        md: "16px",
        sm: "12px",
        pill: "999px",
      },
      fontSize: {
        // Compact scale aligned with Goofish mobile UI
        xs: ["11px", { lineHeight: "14px" }],
        sm: ["13px", { lineHeight: "18px" }],
        base: ["14px", { lineHeight: "20px" }],
        md: ["15px", { lineHeight: "22px" }],
        lg: ["17px", { lineHeight: "24px" }],
        xl: ["19px", { lineHeight: "26px" }],
        "2xl": ["22px", { lineHeight: "28px" }],
        "3xl": ["26px", { lineHeight: "32px" }],
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: 0, transform: "translateY(6px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out forwards",
      },
    },
  },
  plugins: [animate],
}