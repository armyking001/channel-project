// vite.config.js
import { defineConfig } from "file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/frontend/node_modules/@vitejs/plugin-react/dist/index.js";
var vite_config_default = defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJ6OlxcXFxzb2Z0LVJFRFxcXFxoZXJtZXNcXFxcXHU1RjAwXHU1M0QxXHU4RjZGXHU0RUY2XFxcXFx1NkUyMFx1OTA1M1x1OTg3OVx1NzZFRVx1NzY3Qlx1OEJCMFxcXFxmcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiejpcXFxcc29mdC1SRURcXFxcaGVybWVzXFxcXFx1NUYwMFx1NTNEMVx1OEY2Rlx1NEVGNlxcXFxcdTZFMjBcdTkwNTNcdTk4NzlcdTc2RUVcdTc2N0JcdThCQjBcXFxcZnJvbnRlbmRcXFxcdml0ZS5jb25maWcuanNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL3o6L3NvZnQtUkVEL2hlcm1lcy8lRTUlQkMlODAlRTUlOEYlOTElRTglQkQlQUYlRTQlQkIlQjYvJUU2JUI4JUEwJUU5JTgxJTkzJUU5JUExJUI5JUU3JTlCJUFFJUU3JTk5JUJCJUU4JUFFJUIwL2Zyb250ZW5kL3ZpdGUuY29uZmlnLmpzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcblxuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcbiAgYmFzZTogJy4vJyxcbiAgcGx1Z2luczogW3JlYWN0KCldLFxuICBzZXJ2ZXI6IHtcbiAgICBwb3J0OiA1MTczLFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cDovL2xvY2FsaG9zdDo4MDAwJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgfVxuICAgIH1cbiAgfSxcbiAgYnVpbGQ6IHtcbiAgICBvdXREaXI6ICcuLi9iYWNrZW5kL3N0YXRpYycsXG4gICAgZW1wdHlPdXREaXI6IHRydWUsXG4gIH1cbn0pIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFtWSxTQUFTLG9CQUFvQjtBQUNoYSxPQUFPLFdBQVc7QUFFbEIsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsTUFBTTtBQUFBLEVBQ04sU0FBUyxDQUFDLE1BQU0sQ0FBQztBQUFBLEVBQ2pCLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxRQUNOLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxNQUNoQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxPQUFPO0FBQUEsSUFDTCxRQUFRO0FBQUEsSUFDUixhQUFhO0FBQUEsRUFDZjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
