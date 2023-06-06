import os
from pytezos import pytezos

# Replace 'contract_address' with the actual address of the smart contract you want to index
contract_address = os.environ.get('CONTRACT_ADDRESS')

def index_contract_storage(contract_address):
    # Connect to the Tezos network using the PyTezos library
    pytezos_client = pytezos.using(shell='ghostnet')
    
    # Get the contract's current storage
    contract_storage = pytezos_client.contract(contract_address).storage()
    
    # Index the storage and print the result
    print(contract_storage)

def index_storage(storage):
    # If the storage is a dictionary, iterate over its keys and values
    if isinstance(storage, dict):
        for key, value in storage.items():
            # Print the key and value
            print('Key: {key}, Value: {value} ')
            
            # Recursively index any nested storage
            index_storage(value)
    # If the storage is a list, iterate over its items
    elif isinstance(storage, list):
        for item in storage:
            # Recursively index any nested storage
            index_storage(item)
    # If the storage is a primitive value, print it
    else:
        print('Value: {storage} ')

# Call the function to index the contract storage
index_contract_storage(contract_address)