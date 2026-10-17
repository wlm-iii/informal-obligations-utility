# IOU frontend

React 19 + Vite 7, JavaScript/JSX. The current UI is a branded foundation with the
starter API connectivity example; lending features are not implemented yet.

From the repository root:

```sh
make install
make backend      # terminal 1
make frontend     # terminal 2
```

UI: <http://localhost:5173>. Vite proxies `/api/*` to FastAPI on port 8000 and removes
the prefix. The Docker deployment mounts the API under `/api` as well.

- `src/App.jsx`: current app shell.
- `src/services/`: API hooks (starter demo only).
- `npm run lint`, `npm run build` inside `frontend/`.
- No frontend unit/browser tests yet; add them alongside interactive features.

See [development docs](../docs/DEVELOPMENT.md). Never put secrets in `VITE_*` values;
they become part of the public browser bundle.
