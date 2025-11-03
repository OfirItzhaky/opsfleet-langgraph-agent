## Running Tests

To run the unit tests, install `pytest` and execute from the project root:

```bash
pip install pytest
pytest -q tests
```
If your environment does not recognize the src package (e.g., Windows terminal),
set the Python path before running:
```bash
set PYTHONPATH=.
pytest -q tests
```