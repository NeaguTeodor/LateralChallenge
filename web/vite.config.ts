import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API calls to the docker-compose stack (nginx on :8080).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8080" },
  },
});
