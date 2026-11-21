"""COFP_Token governance guarantees, run against an in-memory EVM.

  1. compile:  node blockchain/tests/compile.js blockchain/COFP_Token.sol /tmp/cofp.json
               (needs `npm i solc@0.8.28` somewhere on NODE_PATH)
  2. test:     COFP_ARTIFACT=/tmp/cofp.json python3 -m unittest blockchain.tests.test_cofp_timelock
               (needs `pip install "web3[tester]"`)
"""
import json
import os
import unittest

ARTIFACT = os.environ.get("COFP_ARTIFACT")
HOUR = 3600
DELAY = 48 * HOUR
GRACE = 14 * 24 * HOUR
SALT = b"\x01" * 32


@unittest.skipUnless(ARTIFACT and os.path.exists(ARTIFACT), "set COFP_ARTIFACT to the compiled contract JSON")
class CofpGovernance(unittest.TestCase):
    def setUp(self):
        from web3 import Web3, EthereumTesterProvider
        self.w3 = Web3(EthereumTesterProvider())
        with open(ARTIFACT) as f:
            art = json.load(f)
        self.owner, self.alice, self.bob = self.w3.eth.accounts[:3]
        C = self.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
        rcpt = self.w3.eth.wait_for_transaction_receipt(C.constructor().transact({"from": self.owner}))
        self.c = self.w3.eth.contract(address=rcpt.contractAddress, abi=art["abi"])
        self.abi_names = {x.get("name") for x in art["abi"]}

    # helpers
    def tx(self, fn, sender):
        return self.w3.eth.wait_for_transaction_receipt(fn.transact({"from": sender}))

    def reverts(self, fn, sender, text):
        with self.assertRaises(Exception) as cm:
            fn.transact({"from": sender})
        self.assertIn(text, str(cm.exception))

    def wait(self, seconds):
        et = self.w3.provider.ethereum_tester
        et.time_travel(self.w3.eth.get_block("latest").timestamp + seconds)
        et.mine_blocks(1)

    # ---- the instant paths are gone ------------------------------------
    def test_old_instant_functions_no_longer_exist(self):
        self.assertNotIn("mint", self.abi_names)
        self.assertNotIn("transferOwnership", self.abi_names)

    # ---- mint -----------------------------------------------------------
    def test_mint_cannot_run_immediately(self):
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "timelock not elapsed")

    def test_mint_runs_after_the_delay_and_only_once(self):
        before = self.c.functions.totalSupply().call()
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.wait(DELAY + 1)
        self.tx(self.c.functions.executeMint(self.alice, 100, SALT), self.owner)
        self.assertEqual(self.c.functions.balanceOf(self.alice).call(), 100)
        self.assertEqual(self.c.functions.totalSupply().call(), before + 100)
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "not queued")

    def test_unqueued_or_altered_mint_is_refused(self):
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "not queued")
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.wait(DELAY + 1)
        # different amount than what was queued
        self.reverts(self.c.functions.executeMint(self.alice, 10**30, SALT), self.owner, "not queued")

    def test_stale_mint_expires(self):
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.wait(DELAY + GRACE + HOUR)
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "expired")

    def test_queued_action_can_be_cancelled(self):
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        # recompute the id the same way the contract does
        from eth_abi import encode
        from web3 import Web3
        mint_id = Web3.keccak(encode(["string", "address", "uint256", "bytes32"], ["mint", self.alice, 100, SALT]))
        self.tx(self.c.functions.cancelQueued(mint_id), self.owner)
        self.wait(DELAY + 1)
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "not queued")

    def test_only_the_owner_can_queue_or_execute(self):
        self.reverts(self.c.functions.queueMint(self.bob, 100, SALT), self.bob, "not the owner")
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.wait(DELAY + 1)
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.bob, "not the owner")

    # ---- ownership -----------------------------------------------------
    def test_ownership_moves_only_after_the_delay(self):
        self.tx(self.c.functions.queueOwnershipTransfer(self.alice, SALT), self.owner)
        self.reverts(self.c.functions.executeOwnershipTransfer(self.alice, SALT), self.owner, "timelock not elapsed")
        self.assertEqual(self.c.functions.owner().call(), self.owner)
        self.wait(DELAY + 1)
        self.tx(self.c.functions.executeOwnershipTransfer(self.alice, SALT), self.owner)
        self.assertEqual(self.c.functions.owner().call(), self.alice)
        # the old key is now powerless
        self.reverts(self.c.functions.queueMint(self.owner, 1, SALT), self.owner, "not the owner")

    # ---- pause ---------------------------------------------------------
    def test_pause_is_immediate_and_stops_everything(self):
        self.tx(self.c.functions.transfer(self.alice, 1000), self.owner)
        self.tx(self.c.functions.approve(self.bob, 500), self.alice)
        self.tx(self.c.functions.queueMint(self.alice, 100, SALT), self.owner)
        self.wait(DELAY + 1)

        self.tx(self.c.functions.pause(), self.owner)  # no delay

        self.reverts(self.c.functions.transfer(self.bob, 1), self.alice, "paused")
        self.reverts(self.c.functions.transferFrom(self.alice, self.bob, 1), self.bob, "paused")
        self.reverts(self.c.functions.burn(1), self.alice, "paused")
        self.reverts(self.c.functions.burnFrom(self.alice, 1), self.bob, "paused")
        self.reverts(self.c.functions.executeMint(self.alice, 100, SALT), self.owner, "paused")

        self.tx(self.c.functions.unpause(), self.owner)
        self.tx(self.c.functions.transfer(self.bob, 1), self.alice)

    # ---- unchanged TRC-20 behaviour -----------------------------------
    def test_basic_token_behaviour_is_intact(self):
        supply = 100_000_000 * 10**18
        self.assertEqual(self.c.functions.totalSupply().call(), supply)
        self.tx(self.c.functions.transfer(self.alice, 5), self.owner)
        self.tx(self.c.functions.burn(2), self.alice)
        self.assertEqual(self.c.functions.balanceOf(self.alice).call(), 3)
        self.assertEqual(self.c.functions.totalSupply().call(), supply - 2)


if __name__ == "__main__":
    unittest.main()
