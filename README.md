# api-contract-tester

A local **API contract enforcement tool**. Point it at an OpenAPI 3.x spec and
a live endpoint, and it calls the endpoint, validates the JSON response against
the schema the spec declared for that operation, and persists every run with
its violations. The dashboard is a FastAPI + vanilla JS app that reads straight
from the stored results.

The pipeline is three stages:

```
ingest                            enforce                         visualize
──────                            ───────                         ───────────
store the OpenAPI spec            call the live endpoint with     dashboard reads stored
(JSON or YAML), verify it         httpx, validate the 200 JSON    runs, per-test drift
parses and has paths              body against the declared       scores, and violation
   │                               schema                          details
   └───────────────────────────────►│◄──────────────────────────────┘
                                    FastAPI + SQLAlchemy
```

- **Ingest** — `POST /api/specs` accepts JSON or YAML spec text. The server
  parses it before storing, so a broken spec never enters the database.
- **Enforce** — `POST /api/tests` takes a spec id, a live endpoint URL, an HTTP
  method, and the spec path (e.g. `/users/{id}`). It resolves the operation's
  200 `application/json` schema, including local `$ref` pointers into
  `components/schemas`, converts it to JSON Schema, makes the real HTTP call,
  and validates the body with `jsonschema`. Each violation is stored as its own
  result row.
- **Visualize** — the dashboard shows spec counts, run history with pass/fail
  status, drift scores, and per-test violation summaries. No canned data.

## Honest scope

This tool validates one thing: does the live 200 response body match what the
spec promised for that operation? A few boundaries worth knowing up front:

- Only the `200` (or `default`) `application/json` schema is checked. Request
  bodies, auth headers, and other status codes are out of scope.
- `$ref` resolution is local to the document (`#/components/schemas/...`).
  External spec files or remote references are not followed.
- A violation counts as **breaking** when it changes the shape consumers rely
  on: a missing required field or a type mismatch. Extra properties, enum
  misses, and length constraints are reported but not breaking.
- The endpoint URL you pass is called as-is. There is no auth, retry logic, or
  rate limiting. Point it at local or trusted services.

## Requirements

- Python 3.11+

Install deps:

```bash
pip install -r requirements.txt
```

## Run the demo server

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> for the dashboard. Ingest a spec, then run a test
against any endpoint that implements it:

```bash
curl -s http://127.0.0.1:8000/api/specs \
  -H 'Content-Type: application/json' \
  -d '{"name":"users-api","version":"1.0.0","content":"@spec.json"}'

curl -s http://127.0.0.1:8000/api/tests \
  -H 'Content-Type: application/json' \
  -d '{"spec_id":1,"endpoint_url":"http://127.0.0.1:9000/users/1","method":"GET","path":"/users/{id}"}'
```

A clean run stores a passing test with zero violations. A drifting response
stores one violation row per mismatch, each with the field path, the type the
spec expected, and the type that actually came back.

### Configuration (environment)

| Variable       | Default                 | Purpose                          |
|----------------|-------------------------|----------------------------------|
| `DATABASE_URL` | local SQLite file       | SQLAlchemy connection string     |

### API

| Method | Path                       | Returns                                |
|--------|----------------------------|----------------------------------------|
| GET    | `/api/health`              | Service status                         |
| POST   | `/api/specs`               | Store a spec (400 if it does not parse)|
| GET    | `/api/specs`               | All stored specs                       |
| GET    | `/api/specs/{id}`          | One stored spec                        |
| DELETE | `/api/specs/{id}`          | Delete a spec                          |
| POST   | `/api/tests`               | Run enforcement, store run + violations|
| GET    | `/api/tests`               | All stored runs                        |
| GET    | `/api/tests/{id}`          | One stored run                         |
| GET    | `/api/results`             | Per-test drift summaries               |
| GET    | `/api/results/{test_id}`   | Detailed violation rows for a run      |
| GET    | `/api/contract/dashboard`  | Aggregate counts for the stat cards    |

## Library usage

The enforcer does not need FastAPI or SQLAlchemy, so you can import it directly:

```python
from backend.services.contract_enforcer import enforce_contract

violations = enforce_contract(
    spec_content=open("spec.json").read(),
    method="GET",
    endpoint_url="http://127.0.0.1:9000/users/1",
    path="/users/{id}",
)
for v in violations:
    print(v.field_name, v.expected_type, "->", v.actual_type, v.breaking_change)
```

## Docker

```bash
docker compose up --build
```

This runs the app plus a Postgres store. The app binds `0.0.0.0` inside the
container; compose maps the port to the host's loopback only, so the service
stays local.

## Tests

```bash
python -m pytest tests -q
```

The suite covers the pure enforcer (spec parsing, `$ref` resolution, schema
conversion, violation classification), the storage-backed API through
`TestClient`, and two live enforcement runs against a real uvicorn server on a
random port: one endpoint that honors the contract and one that drifts. It uses
`tmp_path` fixtures throughout, so no machine-specific paths are baked in and
no external service is required.

## License

MIT, see [LICENSE](LICENSE).
