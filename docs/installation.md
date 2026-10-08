# Installation

`compas_usd` depends on [`usd-core`](https://pypi.org/project/usd-core/), Pixar's official OpenUSD wheels
(no imaging/Hydra). Wheels exist for CPython 3.9+ on macOS (universal2), Linux x86-64 and Windows x86-64.

## Latest

```bash
git clone https://github.com/compas-dev/compas_usd.git
cd compas_usd
pip install -e .
```

## Development

```bash
pip install -e ".[dev]"
invoke test
invoke lint
```

Inside an application that ships its own USD build (Omniverse, Houdini, Maya), install without dependencies
(`pip install --no-deps -e .`) so that the host's `pxr` is used.
