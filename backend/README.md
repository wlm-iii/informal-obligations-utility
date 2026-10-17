# IOU backend

Python 3.12 + FastAPI, with SQLAlchemy/Psycopg and Alembic scaffolding for PostgreSQL 17.
No domain models or lending features exist yet.

From the repository root:

```sh
make install
make db-init
make db-start
make migrate
make backend
```

The app is `backend/src/iou/api.py`; API docs are at <http://127.0.0.1:8000/docs>.
`src/api.py` is a compatibility entry point. `src/main.py` mounts the API and built
frontend for the Docker deployment. Importing the API does not connect to PostgreSQL.

Tests: `make test` (no database), `make test-db` (disposable database required).
Linters: `make lint`. See [development docs](../docs/DEVELOPMENT.md) and
[product spec](../docs/SPEC.md).
