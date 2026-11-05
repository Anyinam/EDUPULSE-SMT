# EduPulse SMT Frontend

## Local API Setup

The Vite development server normally forwards `/api` requests to `http://127.0.0.1:5000`. Run the backend for login, registration, password recovery, and school operations, or set `VITE_API_PROXY_TARGET` to your development backend.

For a public-site preview without a local backend, set `VITE_PUBLIC_API_PROXY_TARGET=https://edupulsesmt.com` in an ignored `.env.development.local` file in this directory. Only GET/HEAD requests to `/api/subscription/plans` and `/api/public/platform-content` use this target. Authorization and cookie headers are removed. Account submissions and private APIs continue to use the local backend and are never forwarded to production by this option.

Run `npm run dev`, `npm test -- --run`, and `npm run build` from this directory. Vite reloads when its configuration changes; refresh the browser after the server is ready.

Password-reset emails use the backend's `FRONTEND_URL`, then `FRONTEND_ORIGIN`, with a localhost fallback for development. Configure a public frontend URL in production.

## Lightweight online-first PWA

The frontend is installable from the same HTTPS origin as the website. `public/manifest.webmanifest` provides the app metadata, and `public/service-worker.js` caches the app shell plus frontend assets under `/assets/` and `/images/`.

The service worker deliberately does not intercept `/api` requests or cache authenticated responses and school records. Dashboards that depend on current server data—including kitchen meal counts based on homeroom attendance—remain online features. When the browser reports a connection loss, the app displays a warning that data may be stale; on reconnection, staff are prompted to refresh dashboards.

The service worker is served from `/service-worker.js` at the site root and requires HTTPS in production (localhost is supported for development). Configure the hosting layer to serve that file with revalidation/no-cache headers so deployed service-worker updates can be detected; do not rewrite it to the SPA HTML fallback. This PWA improves startup and repeat-visit bandwidth, but does not provide offline dashboard data entry or background synchronization.

Validate changes with `npm test -- --run` and `npm run build` from this directory. The generated `dist/` output must be deployed to the same origin as `edupulsesmt.com`.

## Toolchain

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
