from dataclasses import dataclass, field
import json
import logging
from os import getenv
from pathlib import Path
from time import sleep
from typing import List, Literal, Optional, Type, Union
from pycardano import transaction
from pycardano.address import Address

from pycardano.backend.base import ChainContext
from pycardano.backend.blockfrost import BlockFrostChainContext
from pycardano.exception import PyCardanoException
from pycardano.hash import TransactionId
from pycardano.key import (
    PaymentKeyPair,
    PaymentSigningKey,
    PaymentVerificationKey,
    SigningKey,
    VerificationKey,
)
from pycardano.logging import logger
from pycardano.nativescript import NativeScript
from pycardano.network import Network
from pycardano.transaction import TransactionOutput, UTxO, Value
from pycardano.txbuilder import TransactionBuilder


# set logging level to info
logger.setLevel(logging.INFO)


class Amount:
    """Base class for Cardano currency amounts."""

    def __init__(self, amount=0, amount_type="lovelace"):

        self._amount = amount
        self._amount_type = amount_type

        if self._amount_type == "lovelace":
            self.lovelace = int(self._amount)
            self.ada = self._amount / 1000000
        else:
            self.lovelace = int(self._amount * 1000000)
            self.ada = self._amount

        self._amount_dict = {"lovelace": self.lovelace, "ada": self.ada}

    @property
    def amount(self):

        if self._amount_type == "lovelace":
            return self.lovelace
        else:
            return self.ada

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return self.amount == other
        elif isinstance(other, Amount):
            return self.lovelace == other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __ne__(self, other):
        if isinstance(other, (int, float)):
            return self.amount != other
        elif isinstance(other, Amount):
            return self.lovelace != other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __gt__(self, other):
        if isinstance(other, (int, float)):
            return self.amount > other
        elif isinstance(other, Amount):
            return self.lovelace > other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __lt__(self, other):
        if isinstance(other, (int, float)):
            return self.amount < other
        elif isinstance(other, Amount):
            return self.lovelace < other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __ge__(self, other):
        if isinstance(other, (int, float)):
            return self.amount >= other
        elif isinstance(other, Amount):
            return self.lovelace >= other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __le__(self, other):
        if isinstance(other, (int, float)):
            return self.amount <= other
        elif isinstance(other, Amount):
            return self.lovelace <= other.lovelace
        else:
            raise TypeError("Must compare with a number or another Cardano amount")

    def __int__(self):
        return int(self.amount)

    def __str__(self):
        return str(self.amount)

    def __hash__(self):
        return hash((self._amount, self._amount_type))

    def __bool__(self):
        return bool(self._amount)

    def __getitem__(self, key):
        return self._amount_dict[key]

    # Math
    def __add__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount + other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount + other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __radd__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount + other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount + other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount - other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount - other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount - other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount - other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount * other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount * other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount * other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount * other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount / other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount / other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __floordiv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount // other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount // other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount / other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount / other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __rfloordiv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(self.amount // other)
        elif isinstance(other, Amount):
            return self.__class__(self.amount // other[self._amount_type])
        else:
            raise TypeError("Must compute with a number or another Cardano amount")

    def __neg__(self):
        return self.__class__(-self.amount)

    def __pos__(self):
        return self.__class__(+self.amount)

    def __abs__(self):
        return self.__class__(abs(self.amount))

    def __round__(self):
        return self.__class__(round(self.amount))


class Lovelace(Amount):
    def __init__(self, amount=0):
        super().__init__(amount, "lovelace")

    def __repr__(self):
        return f"Lovelace({self.lovelace})"

    def as_lovelace(self):
        return Lovelace(self.lovelace)

    def as_ada(self):
        return Ada(self.ada)


class Ada(Amount):
    def __init__(self, amount=0):
        super().__init__(amount, "ada")

    def __repr__(self):
        return f"Ada({self.ada})"

    def as_lovelace(self):
        return Lovelace(self.lovelace)

    def ad_ada(self):
        return Ada(self.ada)


@dataclass(unsafe_hash=True)
class Token:
    policy: Union[NativeScript, str]
    amount: int
    name: Optional[str] = field(default="")
    hex_name: Optional[str] = field(default="")
    metadata: Optional[dict] = field(default=None, compare=False)

    def __post_init__(self):

        if not isinstance(self.amount, int):
            raise TypeError("Expected token amount to be of type: integer.")

        if self.hex_name:
            if isinstance(self.hex_name, str):
                self.name = bytes.fromhex(self.hex_name).decode("utf-8")

        elif isinstance(self.name, str):
            self.hex_name = bytes(self.name.encode("utf-8")).hex()

    def __str__(self):
        return self.name


@dataclass
class Wallet:
    """An address for which you own the keys or will later create them."""

    name: str
    address: Optional[Union[Address, str]] = None
    keys_dir: Optional[Union[str, Path]] = field(repr=False, default=Path("./priv"))
    network: Optional[Literal["mainnet", "testnet"]] = "mainnet"

    # generally added later
    lovelace: Optional[Lovelace] = field(repr=False, default=Lovelace(0))
    ada: Optional[Ada] = field(repr=True, default=Ada(0))
    signing_key: Optional[SigningKey] = field(repr=False, default=None)
    verification_key: Optional[VerificationKey] = field(repr=False, default=None)
    uxtos: Optional[list] = field(repr=False, default_factory=list)
    policy: Optional[NativeScript] = field(repr=False, default=None)

    def __post_init__(self):

        # convert address into pycardano format
        if isinstance(self.address, str):
            self.address = Address.from_primitive(self.address)

        if isinstance(self.keys_dir, str):
            self.keys_dir = Path(self.keys_dir)

        # if not address was provided, get keys
        if not self.address:
            self._load_or_create_key_pair()
        # otherwise derive the network from the address provided
        else:
            self.network = self.address.network.name.lower()

    def query_utxos(self, context: ChainContext):

        try:
            self.utxos = context.utxos(str(self.address))
        except Exception as e:
            logger.debug(
                f"Error getting UTxOs. Address has likely not transacted yet. Details: {e}"
            )
            self.utxos = []

        # calculate total ada
        if self.utxos:

            self.lovelace = Lovelace(
                sum([utxo.output.amount.coin for utxo in self.utxos])
            )
            self.ada = self.lovelace.as_ada()

            # add up all the tokens
            self._get_tokens()

            logger.debug(
                f"Wallet {self.name} has {len(self.utxos)} UTxOs containing a total of {self.ada} ₳."
            )

        else:
            logger.debug(f"Wallet {self.name} has no UTxOs.")

            self.lovelace = Lovelace(0)
            self.ada = Ada(0)

    @property
    def stake_address(self):

        if isinstance(self.address, str):
            address = Address.from_primitive(self.address)
        else:
            address = self.address

        return Address.from_primitive(
            bytes.fromhex(f"e{address.network.value}" + str(address.staking_part))
        )

    @property
    def verification_key_hash(self):
        return str(self.address.payment_part)

    @property
    def tokens(self):
        return self._token_list

    @property
    def tokens_dict(self):
        return self._token_dict

    def _load_or_create_key_pair(self):

        if not self.keys_dir.exists():
            self.keys_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Creating directory {self.keys_dir}.")

        skey_path = self.keys_dir / f"{self.name}.skey"
        vkey_path = self.keys_dir / f"{self.name}.vkey"

        if skey_path.exists():
            skey = PaymentSigningKey.load(str(skey_path))
            vkey = PaymentVerificationKey.from_signing_key(skey)
            logger.info(f"Wallet {self.name} found.")
        else:
            key_pair = PaymentKeyPair.generate()
            key_pair.signing_key.save(str(skey_path))
            key_pair.verification_key.save(str(vkey_path))
            skey = key_pair.signing_key
            vkey = key_pair.verification_key
            logger.info(f"New wallet {self.name} created in {self.keys_dir}.")

        self.signing_key = skey
        self.verification_key = vkey

        self.address = Address(vkey.hash(), network=Network[self.network.upper()])

    def _get_tokens(self):

        # loop through the utxos and sum up all tokens
        tokens = {}

        for utxo in self.utxos:

            for script_hash, assets in utxo.output.amount.multi_asset.items():

                policy_id = str(script_hash)

                for asset, amount in assets.items():

                    asset_name = asset.to_primitive().decode("utf-8")

                    if not tokens.get(policy_id):
                        tokens[policy_id] = {}

                    if not tokens[policy_id].get(asset_name):
                        tokens[policy_id][asset_name] = amount
                    else:
                        current_amount = tokens[policy_id][asset_name]
                        tokens[policy_id][asset_name] = current_amount + amount

        # Convert asset dictionary into Tokens
        token_list = []
        for policy_id, assets in tokens.items():
            for asset, amount in assets.items():
                token_list.append(Token(policy_id, amount=amount, name=asset))

        self._token_dict = tokens
        self._token_list = token_list

    def get_utxo_creators(self, context: ChainContext):

        for utxo in self.utxos:
            utxo.creator = get_utxo_creator(utxo, context)


# helpers
def get_utxo_creator(utxo: UTxO, context: ChainContext):

    if isinstance(context, BlockFrostChainContext):
        utxo_creator = (
            context.api.transaction_utxos(str(utxo.input.transaction_id))
            .inputs[0]
            .address
        )

        return utxo_creator


def get_stake_address(address: Union[str, Address]):

    if isinstance(address, str):
        address = Address.from_primitive(address)

    return Address.from_primitive(
        bytes.fromhex(f"e{address.network.value}" + str(address.staking_part))
    )


def list_all_wallets(wallet_path: Union[str, Path] = Path("./priv")):

    if isinstance(wallet_path, str):
        wallet_path = Path(wallet_path)

    wallets = [skey.stem for skey in list(wallet_path.glob("*.skey"))]

    return wallets
