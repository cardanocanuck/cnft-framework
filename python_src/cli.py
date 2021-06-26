from dotenv import load_dotenv
import atexit
import psycopg2
#import pika
from os import getenv
from time import sleep

from cardano_tools import ShelleyTools

import constants
import tools.db_sync_tools as ds
from classes.token import doggie_token_constructor
#from tools.queue import get_channel, get_channel_info
from tools.scripts.dogs_maintenance import derive_price
from tools.cardano_cli_extra import mint_and_send, make_policy


load_dotenv()
shelley = ShelleyTools(
            getenv("CARDANO_CLI"),
            getenv("CARDANO_NODE_SOCKET"),
            getenv("PRIVATE_FOLDER"),
            network=getenv("NETWORK_MAGIC"))

db_sync = psycopg2.connect(getenv("CARDANO_DB_SYNC_POSTGRES_URL"))
db_tokens = None
if getenv("TOKENS_DB_URL"):
    db_tokens = psycopg2.connect(getenv("TOKENS_DB_URL"))
constants.initiate_constants(shelley)




def failsafe():
    # Do some basic asserts to ensure we're safe
    assert len(constants.STORAGE_ADDRESS) > 20


def create_keys():
    # Create the keys, address, minting policy
    # !This will override existing keys!
    shelley.make_address(constants.MINTING_WALLET)
    make_policy(shelley, constants.MINTING_POLICY)


def onexit():
    try:
        db_sync.close()
    except e:
        pass
    print("Gracefully closed connections")

def mint_dogs(dog_ids, to_address):
    utxo = shelley.get_utxos(constants.MINTING_SENDER_ONLY_ADDRESS)[0]

    # We assume utxo is fat enough. TODO: do not assume
    tx_hash = utxo['TxHash']
    tx_ix = utxo['TxIx']
    tx_available_amount = utxo['Lovelace']

    to_be_minted = []

    # Find the matching doggie if any
    with db_tokens.cursor() as c:
        for dog_id in dog_ids:
            c.execute("SELECT id, doggie_metadata, doggie_id FROM metadata_doggies WHERE (doggie_id = %s) AND (is_visible = FALSE)", (dog_id,))
            if not c.rowcount:
                raise Exception('Bad dog id')


            idx, doggie_metadata, doggie_id = c.fetchone()

            t = doggie_token_constructor(doggie_id, doggie_metadata)
            to_be_minted.append(t)

    # Time to mint and send
    trans_results = mint_and_send(
                    shelley,
                    utxo,
                    to_address,
                    constants.MINTING_SENDER_ONLY_ADDRESS,
                    to_be_minted,
                    wallet_key=constants.MINTING_SENDER_ONLY_KEY
                 )

    with db_tokens.cursor() as c:
        for dog_id in dog_ids:
            c.execute("UPDATE metadata_doggies SET is_visible = TRUE where doggie_id = %s", (dog_id,))

    db_tokens.commit()


def onexit():
    try:
        db_sync.close()
    except e:
        pass
    print("Gracefully closed connections")




atexit.register(onexit)

failsafe()

from tools.scripts import image_tools

