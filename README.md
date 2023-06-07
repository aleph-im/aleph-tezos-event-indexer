# ALEPH.IM : Tezos Event Indexer

Tezos Event Indexer for Aleph.im protocol.

## Prequisities

The following software is a requirement for running this project locally.
The specified versions are those currently in use for this software.
Recommended versions are specified as `same or higher`.

- Docker 24.0.1
- Docker Compose 2.18.1

If running locally without Docker :

- Python 3.10.11
    - Pip 23.1.2

The above modules can be installed via the following command :

```bash
pip install -r requirements.txt
```

Note that some modules may not be compatible with Apple's M1-based hardware.

## Using the Tezos Event Indexer :

### Running locally

```bash
python run.py
```

### Running locally in Docker

```bash
docker-compose -f docker/docker-compose.yaml up
```

## Known issues :

### Python 3.11 and newer package versions incompatibility

Package version management fails on Python 3.11 (and higher) because of dependencies between packages.
Updating some package versions results in the same errors too.

The following issues appear when either upgrading the package versions, or upgrading Python's version.
- https://foss.heptapod.net/pypy/pypy/-/issues/2687
- https://github.com/wbolster/plyvel/issues/100
- https://github.com/tiangolo/fastapi/discussions/6230
- https://github.com/wbolster/plyvel/issues/27
- https://github.com/baking-bad/pytezos/issues/284
- https://github.com/pydantic/pydantic/releases/tag/v1.10.0a1

### Poetry (package manager) incompatibility

Same as above + some Aleph packages do not have a proper definition on Pipfile :
- https://github.com/aleph-im/aleph-client/pull/100

### Mac M1 : Fix errors on Pyvel (if using Brew)

```bash
export LIBRARY_PATH="$LIBRARY_PATH:$(brew --prefix)/lib"
export CPATH="$CPATH:$(brew --prefix)/include"
```