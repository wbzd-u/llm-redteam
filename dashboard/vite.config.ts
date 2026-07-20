import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("@mui/x-charts")) return "charts";
          if (id.includes("@mui/material") || id.includes("@emotion")) return "mui";
        },
      },
    },
  },
});
