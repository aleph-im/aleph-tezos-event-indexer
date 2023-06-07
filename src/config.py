from pydantic import BaseSettings

class Settings(BaseSettings):
    db_folder: str = "/data/events"
    well_contract: str = "KT1ReVgfaUqHzWWiNRfPXQxf7TaBLVbxrztw"
    until_block: int = 0
    rpc_endpoint: str = "https://rpc.tzkt.io/ghostnet"
    trusted_rpc_endpoint: str = "https://rpc.tzkt.io/ghostnet"
    host: str = "127.0.0.1"
    port: int = 8080
    concurrent_job: int = 2
    batch_size: int = 5
    pubsub: dict = None
    objects: str = "events"

    # balances
    aleph_api_server: str = "https://api2.aleph.im"
    aleph_channel: str = "TEST"
    token_symbol: str = "ALEPH"
    chain_name: str = "TEZOS"
    filter_tag: str = "mainnet"
    balances_post_type: str = "balances-update"
    token_address: str = ""
    token_ids: list = []
    ethereum_pkey: str = ""
    ethereum_api_server: str = None

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

config = Settings()
