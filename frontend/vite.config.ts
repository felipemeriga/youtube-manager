import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy vendor libs into their own chunks so they can be cached
        // independently of app code. MUI + icons dominate bundle size; markdown
        // and supabase change rarely. Function form is required because MUI is
        // imported via deep paths (e.g. @mui/material/Button) — the array form
        // only matches top-level package specifiers.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@mui/icons-material")) return "vendor-mui-icons";
          if (id.includes("@mui/material") || id.includes("@emotion"))
            return "vendor-mui";
          if (id.includes("react-markdown") || id.includes("remark-")
              || id.includes("micromark") || id.includes("mdast-util")
              || id.includes("hast-util") || id.includes("unist-"))
            return "vendor-markdown";
          if (id.includes("@supabase")) return "vendor-supabase";
          if (id.includes("react-router")) return "vendor-router";
          if (id.includes("/react/") || id.includes("/react-dom/"))
            return "vendor-react";
          return undefined;
        },
      },
    },
  },
});
