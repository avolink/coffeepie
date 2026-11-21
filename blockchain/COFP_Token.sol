// SPDX-License-Identifier: MIT
// Coffee Pie — COFP Token (TRC-20 on TRON)
// Monetary Policy: Elastic supply. Initial supply of 100'000'000 COFP.
// Tokens are emitted at a rate of 1 COFP per 1 Slice served for 1 minute
// by Providers on the QFDM Network. Dormant Slices (powered off/suspended, but
// still reserving SSD/HDD) emit at the reduced Parking Fee rate of 1.5 COFP per
// Slice per hour. No supply cap — supply grows with the network.
// Emission amounts are computed off-chain by the backend (see payments/models.py)
// and minted via mint(); this contract intentionally stays a thin TRC-20.
// Governance: mint and ownership transfer go through a 48-hour timelock (queue,
// wait, execute) so a stolen owner key cannot create tokens or take the contract
// instantly: the community has two days to see the queued action and react. The
// owner is meant to be a Gnosis Safe multi-sig (see DEPLOY.md Step 6). pause()
// stays immediate, because an emergency brake that waits 48 hours is no brake.
// Deployable via Remix IDE + TronLink wallet.
// Target: TRON Mainnet (chain ID 728126428)

pragma solidity ^0.8.20;

contract COFP_Token {
    string public name = "Coffee Pie";
    string public symbol = "COFP";
    uint8 public decimals = 18;
    uint256 public constant INITIAL_SUPPLY = 100_000_000 * 10 ** 18;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public owner;
    bool public paused;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Burn(address indexed burner, uint256 value);
    event Mint(address indexed to, uint256 value);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address account);
    event Unpaused(address account);
    event ActionQueued(bytes32 indexed id, uint256 executableAt);
    event ActionCancelled(bytes32 indexed id);

    // ── Timelock ──────────────────────────────────────────────────────
    uint256 public constant TIMELOCK_DELAY = 48 hours;
    // A queued action that is not executed within this window expires and has
    // to be queued again, so an old forgotten proposal cannot be fired later.
    uint256 public constant TIMELOCK_GRACE = 14 days;
    // action id => earliest execution time (0 = not queued)
    mapping(bytes32 => uint256) public queuedUntil;

    modifier onlyOwner() {
        require(msg.sender == owner, "COFP: caller is not the owner");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "COFP: token is paused");
        _;
    }

    constructor() {
        owner = msg.sender;
        totalSupply = INITIAL_SUPPLY;
        balanceOf[msg.sender] = INITIAL_SUPPLY;
        emit Transfer(address(0), msg.sender, INITIAL_SUPPLY);
    }

    // ── TRC-20 ────────────────────────────────────────────────────────

    function transfer(address _to, uint256 _value) public whenNotPaused returns (bool) {
        require(_to != address(0), "COFP: transfer to zero address");
        require(balanceOf[msg.sender] >= _value, "COFP: insufficient balance");
        balanceOf[msg.sender] -= _value;
        balanceOf[_to] += _value;
        emit Transfer(msg.sender, _to, _value);
        return true;
    }

    function approve(address _spender, uint256 _value) public returns (bool) {
        allowance[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    function transferFrom(address _from, address _to, uint256 _value) public whenNotPaused returns (bool) {
        require(balanceOf[_from] >= _value, "COFP: insufficient balance");
        require(allowance[_from][msg.sender] >= _value, "COFP: insufficient allowance");
        balanceOf[_from] -= _value;
        balanceOf[_to] += _value;
        allowance[_from][msg.sender] -= _value;
        emit Transfer(_from, _to, _value);
        return true;
    }

    // ── Burning ───────────────────────────────────────────────────────

    function burn(uint256 _value) public whenNotPaused returns (bool) {
        require(balanceOf[msg.sender] >= _value, "COFP: insufficient balance to burn");
        balanceOf[msg.sender] -= _value;
        totalSupply -= _value;
        emit Burn(msg.sender, _value);
        emit Transfer(msg.sender, address(0), _value);
        return true;
    }

    function burnFrom(address _from, uint256 _value) public whenNotPaused returns (bool) {
        require(balanceOf[_from] >= _value, "COFP: insufficient balance to burn");
        require(allowance[_from][msg.sender] >= _value, "COFP: insufficient allowance");
        balanceOf[_from] -= _value;
        allowance[_from][msg.sender] -= _value;
        totalSupply -= _value;
        emit Burn(_from, _value);
        emit Transfer(_from, address(0), _value);
        return true;
    }

    // ── Mint (emit new tokens for Providers serving Slices) ───────────
    // Queue now, execute after TIMELOCK_DELAY. `salt` makes two otherwise
    // identical mints distinct (e.g. the same provider paid twice in a month).

    function queueMint(address _to, uint256 _value, bytes32 _salt) public onlyOwner returns (bytes32 id) {
        require(_to != address(0), "COFP: mint to zero address");
        id = keccak256(abi.encode("mint", _to, _value, _salt));
        _queue(id);
    }

    function executeMint(address _to, uint256 _value, bytes32 _salt) public onlyOwner whenNotPaused returns (bool) {
        require(_to != address(0), "COFP: mint to zero address");
        _consume(keccak256(abi.encode("mint", _to, _value, _salt)));
        totalSupply += _value;
        balanceOf[_to] += _value;
        emit Mint(_to, _value);
        emit Transfer(address(0), _to, _value);
        return true;
    }

    // ── Admin ─────────────────────────────────────────────────────────

    function pause() public onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() public onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function queueOwnershipTransfer(address _newOwner, bytes32 _salt) public onlyOwner returns (bytes32 id) {
        require(_newOwner != address(0), "COFP: new owner is zero address");
        id = keccak256(abi.encode("owner", _newOwner, _salt));
        _queue(id);
    }

    function executeOwnershipTransfer(address _newOwner, bytes32 _salt) public onlyOwner {
        require(_newOwner != address(0), "COFP: new owner is zero address");
        _consume(keccak256(abi.encode("owner", _newOwner, _salt)));
        emit OwnershipTransferred(owner, _newOwner);
        owner = _newOwner;
    }

    /// Withdraw a queued action before it runs (wrong amount, compromised proposer...).
    function cancelQueued(bytes32 _id) public onlyOwner {
        require(queuedUntil[_id] != 0, "COFP: action not queued");
        delete queuedUntil[_id];
        emit ActionCancelled(_id);
    }

    function _queue(bytes32 _id) internal {
        require(queuedUntil[_id] == 0, "COFP: action already queued");
        uint256 eta = block.timestamp + TIMELOCK_DELAY;
        queuedUntil[_id] = eta;
        emit ActionQueued(_id, eta);
    }

    function _consume(bytes32 _id) internal {
        uint256 eta = queuedUntil[_id];
        require(eta != 0, "COFP: action not queued");
        require(block.timestamp >= eta, "COFP: timelock not elapsed");
        require(block.timestamp <= eta + TIMELOCK_GRACE, "COFP: queued action expired");
        delete queuedUntil[_id];
    }
}
