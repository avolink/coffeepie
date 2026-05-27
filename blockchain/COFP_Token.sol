// SPDX-License-Identifier: MIT
// Coffee Pie — COFP Token (TRC-20 on TRON)
// Monetary Policy: Algorithmic emission with community-governed rate.
// Deployable via Remix IDE + TronLink wallet.
// Target: TRON Mainnet (chain ID 728126428)

pragma solidity ^0.8.20;

contract COFP_Token {
    string public name = "Coffee Pie";
    string public symbol = "COFP";
    uint8 public decimals = 0;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public owner;

    // Monetary policy — inflation-targeting
    // targetInflationBasisPoints: e.g. 200 = 2.00% annual inflation
    // annualEmissionCap = totalSupply * targetInflationBasisPoints / 10000
    // Minimum 100 (1%), maximum 500 (5%) enforced at contract level
    uint256 public targetInflationBasisPoints;
    uint256 public emittedThisYear;
    uint256 public yearStart;

    bool public paused;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Burn(address indexed burner, uint256 value);
    event Mint(address indexed to, uint256 value);
    event EmissionCapUpdated(uint256 oldCap, uint256 newCap);
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

    constructor(uint256 _initialSupply, uint256 _targetInflationBasisPoints) {
        require(_targetInflationBasisPoints >= 100, "COFP: inflation floor is 1%");
        require(_targetInflationBasisPoints <= 500, "COFP: inflation ceiling is 5%");
        owner = msg.sender;
        totalSupply = _initialSupply;
        balanceOf[msg.sender] = _initialSupply;
        targetInflationBasisPoints = _targetInflationBasisPoints;
        yearStart = block.timestamp;
        emit Transfer(address(0), msg.sender, _initialSupply);
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

    // ── Emission ──────────────────────────────────────────────────────

    function _rotateYearIfNeeded() internal {
        if (block.timestamp >= yearStart + 365 days) {
            yearStart = block.timestamp;
            emittedThisYear = 0;
        }
    }

    function annualEmissionCap() public view returns (uint256) {
        return totalSupply * targetInflationBasisPoints / 10000;
    }

    function remainingEmission() public view returns (uint256) {
        if (block.timestamp >= yearStart + 365 days) return annualEmissionCap();
        uint256 cap = annualEmissionCap();
        return cap > emittedThisYear ? cap - emittedThisYear : 0;
    }

    function mint(address _to, uint256 _value) public onlyOwner returns (bool) {
        require(_to != address(0), "COFP: mint to zero address");
        _rotateYearIfNeeded();
        require(emittedThisYear + _value <= annualEmissionCap(), "COFP: exceeds annual emission cap");

        totalSupply += _value;
        balanceOf[_to] += _value;
        emittedThisYear += _value;
        emit Mint(_to, _value);
        emit Transfer(address(0), _to, _value);
        return true;
    }

    function setTargetInflation(uint256 _targetBasisPoints) public onlyOwner {
        require(_targetBasisPoints >= 100, "COFP: inflation floor is 1%");
        require(_targetBasisPoints <= 500, "COFP: inflation ceiling is 5%");
        uint256 oldCap = annualEmissionCap();
        targetInflationBasisPoints = _targetBasisPoints;
        emit EmissionCapUpdated(oldCap, annualEmissionCap());
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
