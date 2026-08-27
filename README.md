# Mini SDS Library

Static site for viewing and downloading the Chemwatch Mini SDS cards in `minis/`.

```bash
python3 serve.py
```

Then open http://127.0.0.1:8000

After adding or replacing PDFs, rebuild the catalog:

```bash
pip install -r requirements.txt
python3 scripts/build_catalog.py
```
