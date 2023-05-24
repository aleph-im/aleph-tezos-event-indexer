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
        - pytezos 3.9.0
        - Jinja2 3.1.2
        - aiohttp 3.8.4
        - asyncio 3.4.3
        - graphene 3.2.2
        - graphql-core 3.2.3
        - plyvel 1.5.0
        - pydantic 1.10.7
        - python-dotenv 1.0.0
        - fastapi 0.95.2
        - uvicorn 0.22.0
        - starlette 0.27.0
        - starlette-graphene3 0.6.0
        - mnemonic 0.20
        - aleph-client 0.5.1
        - web3 6.4.0

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