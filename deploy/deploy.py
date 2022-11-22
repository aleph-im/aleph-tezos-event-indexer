import json
import logging
import os
import inspect

from aleph_client.__main__ import _load_account
from aleph_client.conf import settings
from aleph_client.synchronous import create_program, create_store
from aleph_client.types import StorageEnum
from aleph_message.models.program import Encoding
from typer import echo

logger = logging.getLogger(__name__)


VENV_MESSAGE = "1000ebe0b61e41d5e23c10f6eb140e837188158598049829f2820f830139fc7d"
VENV_IPFS = "QmXfqx52eeYczhsfFYdWMUAnpcKXiofHgGmpNs7Hm29Ndw"

LIB_MESSAGE = "d7cecdeccc916280f8bcbf0c0e82c3638332da69ece2cbc806f9103a0f8befea"
LIB_IPFS = "QmSZEwAAkZkoNPhMVuc5A8rwonQJhFdknC3LygDrGLg2mg"

CHANNEL = "TEZOS"


def create_program_squashfs(path):
    logger.debug("Creating squashfs archive...")
    os.system(f"mksquashfs {path} {path}.squashfs -noappend")
    path = f"{path}.squashfs"
    assert os.path.isfile(path)
    return path


def upload_program(account, program_squashfs_path: str) -> str:
    with open(program_squashfs_path, "rb") as fd:
        logger.debug("Reading file")
        # TODO: Read in lazy mode instead of copying everything in memory
        file_content = fd.read()
        logger.debug("Uploading file")
        result = create_store(
            account=account,
            file_content=file_content,
            storage_engine=StorageEnum.storage,
            channel=CHANNEL,
            guess_mime_type=True,
            ref=None,
        )
        logger.debug("Upload finished")
        echo(f"{json.dumps(result, indent=4)}")
        program_ref = result["item_hash"]
    return program_ref


def main():
    app_directory = "../"

    account = _load_account(None, None)

    program_squashfs_path = create_program_squashfs(app_directory)
    assert os.path.isfile(program_squashfs_path)

    program_ref = upload_program(account, program_squashfs_path)
    #runtime = settings.DEFAULT_RUNTIME_ID
    runtime = "6cc94ab5db14dff4d2f01939a8f1424012bbe0e748be1ec6486ed93d9fdd2680"
    print("Run time default", settings.DEFAULT_RUNTIME_ID)

    volumes = [
        {
            "comment": "Extra lib",
            "mount": "/opt/extra_lib",
            "ref": LIB_MESSAGE,
            "use_latest": True,
        },
        {
            "comment": "Python Virtual Environment",
            "mount": "/opt/packages",
            "ref": VENV_MESSAGE,
            "use_latest": True,
        },
        {
            "comment": "Data storage",
            "mount": "/data",
            "name": "data",
            "size_mib": 512,
            "persistence": "host"
        },
    ]

    environment_variables = {
      "LD_LIBRARY_PATH": "/opt/extra_lib",
      "DB_FOLDER": "/data",
      "RPC_ENDPOINT": "https://rpc.tzkt.io/ithacanet",
      "TRUSTED_RPC_ENDPOINT": "https://rpc.tzkt.io/ithacanet",
      "WELL_CONTRACT": "KT1ReVgfaUqHzWWiNRfPXQxf7TaBLVbxrztw",
      "PORT": "8080",
      "CONCURRENT_JOB": 5,
      "BATCH_SIZE": 30,
      "UNTIL_BLOCK": 201396,
      "PUBSUB": '{"namespace": "tznms","uuid": "tz_uid_1","hook_url": "_domain_or_ip_addess","pubsub_server": "domain_or_ip_address","secret_shared_key": "112secret_key","channel": "storage","running_mode": "readonly"}'
    }

    aleph_api = "https://official.aleph.im"
    result = create_program(
        account=account,
        program_ref=program_ref,
        entrypoint="run:app",
        runtime=runtime,
        environment_variables=environment_variables,
        storage_engine=StorageEnum.storage,
        channel=CHANNEL,
        address=None,
        session=None,
        api_server=settings.API_HOST,
        memory=4000,
        vcpus=4,
        timeout_seconds=300,
        encoding=Encoding.squashfs,
        volumes=volumes,
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    print(inspect.signature(create_program))
    main()
