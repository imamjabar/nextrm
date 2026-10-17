import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas, #F6F5F1)",
        surface: "var(--surface, #FFFFFF)",
        subtle: "var(--surface-subtle, #F0F1EA)",
        ink: "var(--ink, #202720)",
        secondary: "var(--secondary, #525D53)",
        muted: "var(--muted, #5F695F)",
        stroke: "var(--stroke, #DADFD5)",
        control: "var(--control-border, #7C877B)",
        primary: {
          DEFAULT: "var(--primary, #285C3C)",
          hover: "var(--primary-hover, #204D31)",
          soft: "var(--primary-subtle, #EDF3E9)",
        },
        warning: {
          DEFAULT: "var(--warning, #805015)",
          soft: "var(--warning-subtle, #FFF4DE)",
        },
        warn: {
          DEFAULT: "var(--warning, #805015)",
          soft: "var(--warning-subtle, #FFF4DE)",
        },
        danger: {
          DEFAULT: "var(--danger, #A13228)",
          soft: "var(--danger-subtle, #FBEFEC)",
        },
        info: {
          DEFAULT: "var(--info, #285D86)",
          soft: "var(--info-subtle, #EDF3F8)",
        },
      },
      borderRadius: {
        control: "var(--radius-control, 6px)",
        panel: "var(--radius-panel, 10px)",
      },
      boxShadow: {
        xs: "var(--shadow-xs, 0 1px 2px 0 rgb(0 0 0 / 0.05))",
        overlay: "var(--shadow-overlay, 0 12px 36px rgb(32 39 32 / 14%))",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "'Segoe UI'",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
export default config;
