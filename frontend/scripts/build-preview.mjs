import { build } from "vite";
await build({ base: "./", build: { outDir: "dist-preview", rollupOptions: { input: "dashboard-preview.html" } } });
