# IOU backend

Python 3.12 + FastAPI, with SQLAlchemy/Psycopg and Alembic scaffolding for PostgreSQL 17.
No domain models or lending features exist yet.

From the repository root:

```powershell
py -3.12 scripts/dev.py install
py -3.12 scripts/dev.py db-init
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py migrate
py -3.12 scripts/dev.py backend
```

On Linux/macOS replace `py -3.12` with `python3`, or use `make <task>`.
Nix is optional; see the [setup instructions](../docs/DEVELOPMENT.md).

The app is `backend/src/iou/api.py`; API docs are at <http://127.0.0.1:8000/docs>.
`src/api.py` is a compatibility entry point. `src/main.py` mounts the API and built
frontend for the Docker deployment. Importing the API does not connect to PostgreSQL.

Tasks: `test` (no database), `test-db` (disposable database required), and `lint`.
See [development docs](../docs/DEVELOPMENT.md) and
[product spec](../docs/SPEC.md).
