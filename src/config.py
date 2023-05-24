from pydantic import BaseSettings


class Settings(BaseSettings):
    batch_size: int = 5
    concurrent_job: int = 2
    db_folder: str = "/data/events"
    host: str = "127.0.0.1"
    objects: str = "events"
    port: int = 8080
    pubsub: dict = None
    rpc_endpoint: str = "https://rpc.tzkt.io/ghostnet"
    trusted_rpc_endpoint: str = "https://rpc.tzkt.io/ghostnet"
    until_block: int = 0
    well_contract: str = "KT1ReVgfaUqHzWWiNRfPXQxf7TaBLVbxrztw"

    # balances
    aleph_api_server: str = "https://api2.aleph.im"
    aleph_channel: str = "TEST"
    balances_post_type: str = "balances-update"
    chain_name: str = "TEZOS"
    ethereum_api_server: str = None
    ethereum_pkey: str = ""
    filter_tag: str = "mainnet"
    token_address: str = ""
    token_ids: list = []
    token_symbol: str = "ALEPH"


class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"


config = Settings()
