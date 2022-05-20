from pydantic import BaseSettings

class Settings(BaseSettings):
    db_folder: str = "/data/events"
    well_contract: str = "KT1ReVgfaUqHzWWiNRfPXQxf7TaBLVbxrztw"
    rpc_endpoint: str = "https://rpc.tzkt.io/ithacanet"
    port: int = 8080
    concurrent_job: int = 2
    batch_size: int = 5

    class Config:
        env_file = ".env"

config = Settings()
