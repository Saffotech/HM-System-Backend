# HMS Documentation

Two separate guides — **do not mix them**.

| Folder | For who | Start file |
|--------|---------|------------|
| **[backend/](./backend/)** | Backend developers (FastAPI, database) | [backend/README.md](./backend/README.md) |
| **[frontend/](./frontend/)** | Frontend developers (React, API integration) | [frontend/README.md](./frontend/README.md) · [API Reference](./frontend/API-REFERENCE.md) |
| **[Documentation/](./Documentation/)** | Manager / leadership PPT pack (role-wise) | [Documentation/README.md](./Documentation/README.md) |

## Cross-cutting flows

| Doc | Description |
|-----|-------------|
| [flows/receptionist-module.md](./flows/receptionist-module.md) | Receptionist module — check-in, queue, doctor next-patient calls |
| [flows/queue-endpoints-guide.md](./flows/queue-endpoints-guide.md) | **Which “queue” API to use** — OPD billing vs receptionist vs doctor vs nurse |

## Manager presentation pack

For PowerPoint: start at **[Documentation/](./Documentation/)** — overview, roles matrix, patient journey, then one short file per role. Word copies live under `Documentation/Word/` (generate with `python Docs/Documentation/generate_word_pack.py`).

## Source requirements

Original spec: `Fieds and Requirements.docx`
