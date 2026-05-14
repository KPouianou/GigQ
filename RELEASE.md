# Release Checklist

1. Bump `version` in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit and tag: `git tag vX.Y.Z && git push --tags`

## Publish to PyPI

```bash
pip install build twine

python -m build
twine check dist/*
twine upload dist/*
```

For a test run first:

```bash
twine upload --repository testpypi dist/*
# check https://test.pypi.org/project/gigq/
```

## PyPI token

Store in `~/.pypirc`:

```ini
[pypi]
  username = __token__
  password = pypi-...your-token-here...
```

Or pass inline: `twine upload --username __token__ --password <token> dist/*`
