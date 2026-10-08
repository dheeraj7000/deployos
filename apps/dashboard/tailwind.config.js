/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(222.2 84% 4.9%)",
        foreground: "hsl(210 40% 98%)",
        card: "hsl(222.2 84% 6.9%)",
        "card-foreground": "hsl(210 40% 98%)",
        primary: "hsl(217.2 91.2% 59.8%)",
        border: "hsl(217.2 32.6% 17.5%)",
      },
    },
  },
  plugins: [],
};
