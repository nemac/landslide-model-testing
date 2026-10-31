import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Vite does not hot-reload files in public/. The run watcher rewrites public/data (tiles,
// index.json, charts.json) after each landslide finishes, so reload the page when that lands.
// charts.json is written last, index.json just before it; wait a moment so both are complete.
function reloadOnData(): Plugin {
  return {
    name: "reload-on-data",
    configureServer(server) {
      const dir = path.resolve(__dirname, "public/data");
      server.watcher.add(dir);
      let timer: ReturnType<typeof setTimeout> | null = null;
      const onChange = (file: string) => {
        if (!file.startsWith(dir) || !/(index|charts)\.json$/.test(file)) return;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => { server.config.logger.info("data updated, reloading"); server.ws.send({ type: "full-reload" }); }, 2000);
      };
      server.watcher.on("change", onChange);
      server.watcher.on("add", onChange);
    },
  };
}

// base "./" so the built site works from any folder, including GitHub Pages
export default defineConfig({
  plugins: [react(), reloadOnData()],
  base: "./",
});
