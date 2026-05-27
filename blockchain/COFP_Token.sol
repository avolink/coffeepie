// SPDX-License-Identifier: MIT
// Coffee Pie — COFP Token (TRC-20 on TRON)
// Monetary Policy: Fixed supply of 100'000'000 COFP. No inflation. No deflation.
// Re-mint only to restore burned supply (supply <= MAX_SUPPLY).
// Deployable via Remix IDE + TronLink wallet.
// Target: TRON Mainnet (chain ID 728126428)

pragma solidity ^0.8.20;

contract COFP_Token {
    string public name = "Coffee Pie";
    string public symbol = "COFP";
    uint8 public decimals = 18;
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10 ** 18;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public owner;
    bool public paused;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Burn(address indexed burner, uint256 value);
    event Remint(address indexed to, uint256 value);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address account);
    event Unpaused(address account);

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
        totalSupply = MAX_SUPPLY;
        balanceOf[msg.sender] = MAX_SUPPLY;
        emit Transfer(address(0), msg.sender, MAX_SUPPLY);
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

    function burn(uint256 _value) public returns (bool) {
        require(balanceOf[msg.sender] >= _value, "COFP: insufficient balance to burn");
        balanceOf[msg.sender] -= _value;
        totalSupply -= _value;
        emit Burn(msg.sender, _value);
        emit Transfer(msg.sender, address(0), _value);
        return true;
    }

    function burnFrom(address _from, uint256 _value) public returns (bool) {
        require(balanceOf[_from] >= _value, "COFP: insufficient balance to burn");
        require(allowance[_from][msg.sender] >= _value, "COFP: insufficient allowance");
        balanceOf[_from] -= _value;
        allowance[_from][msg.sender] -= _value;
        totalSupply -= _value;
        emit Burn(_from, _value);
        emit Transfer(_from, address(0), _value);
        return true;
    }

    // ── Remint (only to restore burned supply) ────────────────────────

    function remint(address _to, uint256 _value) public onlyOwner returns (bool) {
        require(_to != address(0), "COFP: remint to zero address");
        require(totalSupply + _value <= MAX_SUPPLY, "COFP: remint exceeds MAX_SUPPLY");
        totalSupply += _value;
        balanceOf[_to] += _value;
        emit Remint(_to, _value);
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

    function transferOwnership(address _newOwner) public onlyOwner {
        require(_newOwner != address(0), "COFP: new owner is zero address");
        emit OwnershipTransferred(owner, _newOwner);
        owner = _newOwner;
    }
}
