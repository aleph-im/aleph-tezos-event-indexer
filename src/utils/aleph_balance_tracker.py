from aleph_client.asynchronous import create_post
from aleph_client.chains.ethereum import ETHAccount
from functools import lru_cache
from hexbytes import HexBytes
from src.storage.event import eventStorage
from src.config import config
import json

async def update_balances(account, main_level, balances):
    return await create_post(
        account, {
            'tags': ['TEZOS', 'TOKEN', config.token_address,
                     config.filter_tag],
            'main_height': main_level,
            'platform': '{}_{}'.format(config.token_symbol,
                                       config.chain_name),
            'token_contract': config.token_address,
            'token_symbol': config.token_symbol,
            'chain': config.chain_name,
            'balances': balances
        },
        config.balances_post_type,
        channel=config.aleph_channel,
        api_server=config.aleph_api_server)

@lru_cache(maxsize=2)
def get_aleph_account():
    if config.ethereum_pkey:
        pri_key = HexBytes(config.ethereum_pkey)
        account = ETHAccount(pri_key)
        return account
    else:
        return None
    
async def monitor_process():
    balances = []
    main_level = None
    keys_to_delete = []
    total = 0

    for item in eventStorage.get_changed_balances():
        total += 1
        info = json.loads(item[1])
        if main_level is None:
            main_level = info["account"]["block_level"]

        # avoid wrong balance at different check
        if main_level != info["account"]["block_level"]:
            continue
        
        balances.append({info["account"]["address"]: info["account"]["balance"]})
        keys_to_delete.append(item[0])


    if len(balances) > 0:
        account = get_aleph_account()
        await update_balances(account, main_level, balances)

    for key in keys_to_delete:
        eventStorage.delete_balance(key)

    # check pending balance to post and avoid infinite loop if undexpected error occured
    pending_balances = len(list(eventStorage.get_changed_balances()))
    if pending_balances < total:
        await monitor_process()
