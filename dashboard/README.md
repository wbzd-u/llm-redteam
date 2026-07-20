# Local dashboard

The dashboard follows established Material UI admin/dashboard patterns and keeps the Python workbench as the source of truth. It is intentionally local-only and read-only in v0.1.

```powershell
# Terminal 1: from the repository root
python -m pip install -e .[dashboard]
python -m redteam_memory serve

# Terminal 2
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The API binds to `127.0.0.1:8787` and exposes no credential or target-execution endpoint.
