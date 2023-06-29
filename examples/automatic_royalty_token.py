import datetime as dt
import logging
import time
from pprint import pformat

from pycardano import wallet

# This script mints and burns an NFT royalty token based off of CIP-0027 (https://github.com/cardano-foundation/CIPs/tree/master/CIP-0027)

# 1. Make sure to create a wallet for the policy, with name POLICY_WALLET_NAME
# 2. Create your policy with the name POLICY_NAME and the above wallet as a signer
# 3. Fill out the details below and run the script, make sure your BlockFrost ENV variables are set.

POLICY_NAME = "myPolicy"
POLICY_WALLET_NAME = "myPolicyWallet"

ROYALTY_ADDRESS = "addr_test1qpxh0m34vqkzsaucxx6venpnetgay6ylacuwvrdfdv5wnmw34uylg63pcm2dmsjzx8rrndy0lhwhht2h9f0kt8kv2qrswzxgy0"
ROYALTY_PERCENT = "0.05"

WALLET_NAME = "royaltytest"  # This is a temporary wallet generated by the script to mint the token.
CODED_AMOUNT = wallet.Ada(3.555432)  # pick a random amount between 3 and 4 ADA
NETWORK = "preprod"

# Set up logging!
root = logging.getLogger()
root.setLevel(logging.DEBUG)

logging_timestamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    filename=f"./{WALLET_NAME}.log",
    filemode="a",
)

fh = logging.FileHandler(filename=f"./{WALLET_NAME}.log")
fh.name = "File Logger"
fh.setLevel(logging.DEBUG)
root.addHandler(fh)

# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.name = "Console Logger"
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
root.addHandler(console)


def chunkstring(string, length):
    return (string[0 + i : length + i] for i in range(0, len(string), length))


def create_royalty_metadata(royalty_address: str, royalty_percent: str):
    """Write royalty metadata to a file"""

    metadata = {"777": {}}
    metadata["777"] = {}

    # add rate
    metadata["777"]["rate"] = royalty_percent

    # add address, and split it longer than 64 characters
    if len(royalty_address) > 64:
        metadata["777"]["addr"] = list(chunkstring(royalty_address, 64))
    else:
        metadata["777"]["addr"] = royalty_address

    return metadata


def launch():
    logger = logging.getLogger(__name__)

    logger.info("Welcome to the royalty NFT generation script!")
    logger.info(f"Network: {NETWORK}")

    ORIGINAL_SENDER = None
    DONE = False

    # generate royalty metadata
    royalty_metadata = create_royalty_metadata(ROYALTY_ADDRESS, ROYALTY_PERCENT)

    # create receiving wallet
    tmp_wallet = wallet.Wallet(name="tmp_royalty_wallet", network=NETWORK)
    policy_wallet = wallet.Wallet(name=POLICY_WALLET_NAME, network=NETWORK)
    policy = wallet.TokenPolicy(name=POLICY_NAME)

    logger.info(
        f"Generating a 777 royalty NFT with {ROYALTY_PERCENT}/1 ({float(ROYALTY_PERCENT)*100}%) to address {ROYALTY_ADDRESS}"
    )
    logger.info("Metadata:")
    logger.info(pformat(royalty_metadata))
    time.sleep(2)

    logger.info(
        f"If this looks right, please send exactly {CODED_AMOUNT.ada} ADA to\n {tmp_wallet.address}"
    )
    time.sleep(2)

    while not DONE:
        loop_start_time = dt.datetime.now(dt.timezone.utc)
        logger.info(f"Starting loop {loop_start_time}")

        tmp_wallet.sync()
        tmp_wallet.get_utxo_creators()

        for utxo in tmp_wallet.utxos:
            # check whether or not to mint
            can_mint = False
            if wallet.Lovelace(utxo.output.amount.coin) == CODED_AMOUNT:
                logger.info(
                    f"Coded amount of {CODED_AMOUNT.ada} ADA recieved: can mint 777 token!"
                )
                can_mint = True
            else:
                logger.info(
                    f"Please send exactly {CODED_AMOUNT.ada} ADA to\n {tmp_wallet.address}"
                )

            if can_mint:
                ORIGINAL_SENDER = utxo.creator
                logger.info(
                    f"Original sender of {CODED_AMOUNT.ada} ADA is {ORIGINAL_SENDER}"
                )

                token = wallet.Token(
                    policy=policy, amount=1, name="", metadata=royalty_metadata
                )

                logger.info("Minting token, please wait for confirmation...")

                mint_tx = tmp_wallet.mint_tokens(
                    to=tmp_wallet,
                    mints=token,
                    utxos=utxo,
                    signers=[tmp_wallet, policy_wallet],
                    await_confirmation=True,
                )

                logger.info(f"Mint successful: Tx ID {mint_tx}")
                logger.info(
                    "DO NOT STOP SCRIPT YET! Please wait so we can burn the token."
                )

                continue

            # check if we can burn the token
            can_burn = False
            utxo_tokens = utxo.output.amount.multi_asset

            if utxo_tokens:
                if (
                    len(utxo_tokens) == 1
                    and str(list(utxo_tokens.keys())[0]) == policy.id
                ):
                    logger.info(f"No name token found: can burn 777 token!")
                    logger.info(
                        f"Will send change to original sender: {ORIGINAL_SENDER}"
                    )
                    can_burn = True

            if can_burn:
                # get original sender
                utxo_info = tmp_wallet.context.api.transaction_utxos(
                    str(utxo.input.transaction_id)
                )
                input_utxo = utxo_info.inputs[0].tx_hash
                ORIGINAL_SENDER = (
                    tmp_wallet.context.api.transaction_utxos(str(input_utxo))
                    .inputs[0]
                    .address
                )

                token = wallet.Token(
                    policy=policy,
                    amount=-1,
                    name="",
                )

                logger.info(
                    "Burning the royalty token. Please wait for confirmation..."
                )
                burn_tx = tmp_wallet.mint_tokens(
                    to=ORIGINAL_SENDER,
                    mints=token,
                    signers=[tmp_wallet, policy_wallet],
                    utxos=utxo,
                    change_address=ORIGINAL_SENDER,
                    await_confirmation=True,
                )

                logger.info(f"Burn successful! Tx ID: {burn_tx}")

                DONE = True

                continue

        time.sleep(5)

    logger.info("Your royalties are ready!")
    logger.info(f"https://cardanoscan.io/tokenPolicy/{policy.id}")


if __name__ == "__main__":
    launch()
