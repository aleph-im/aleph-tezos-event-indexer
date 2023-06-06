# ALEPH.IM : Tezos Event Indexer

Tezos Event Indexer for Aleph.im protocol.

## Prequisities

The following software is a requirement for running this project locally.
The following versions are those currently in use for this version.
Recommended versions are specified as `same or higher`.

- Docker 24.0.1
- Docker Compose 2.18.1

If running locally without Docker :

- Python 3.11.3
    - Pip 23.1.2

The above modules can be installed via the following command :

```bash
pip install -r requirements.txt
```

Note that some modules may not be compatible with Apple's M1-based hardware.

## Running locally

```bash
python run.py
```

## Running locally in Docker

```bash
docker-compose -f docker/docker-compose.yaml up
```

## Errors on Pyvel :

```bash
export LIBRARY_PATH="$LIBRARY_PATH:$(brew --prefix)/lib"
export CPATH="$CPATH:$(brew --prefix)/include"
```