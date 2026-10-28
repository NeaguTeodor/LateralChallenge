# web

Customer & staff UI for the takeaway platform — React + TypeScript, built with Vite.

In docker-compose the `nginx` image is built from this folder: the static build is served
at `/` and API calls go to `/api/v1` on the same origin.

## Pages

| Path                 | Who      | What                                              |
|----------------------|----------|---------------------------------------------------|
| `/`                  | public   | Restaurant list                                   |
| `/restaurants/:id`   | public   | Menu + cart; checkout needs an account            |
| `/login`, `/register`| public   | Auth (JWT kept in `localStorage`)                 |
| `/orders`            | user     | Own orders                                        |
| `/orders/:id`        | user     | Live tracking (SSE), step times, cancel if pending |
| `/admin/orders`      | admin    | All orders, filter by status, advance / cancel    |
| `/admin/menus`       | admin    | Add restaurants; add / edit / delete menu items   |

## Local development

```bash
npm install
npm run dev     # http://localhost:5173, proxies /api to the compose stack on :8080
npm run build   # type-check + production build into dist/
```

Set `API_PROXY_TARGET` to point the dev proxy elsewhere (e.g. `http://localhost:8000`
when running uvicorn directly).
