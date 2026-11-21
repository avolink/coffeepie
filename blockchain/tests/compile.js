const solc=require('solc'),fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const out=JSON.parse(solc.compile(JSON.stringify({language:'Solidity',sources:{'C.sol':{content:src}},settings:{optimizer:{enabled:true,runs:200},outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}})));
const errs=(out.errors||[]);errs.forEach(e=>console.error(e.severity+': '+e.formattedMessage));
if(errs.some(e=>e.severity==='error'))process.exit(1);
const c=out.contracts['C.sol']['COFP_Token'];
fs.writeFileSync(process.argv[3],JSON.stringify({abi:c.abi,bytecode:'0x'+c.evm.bytecode.object}));
console.log('compiled OK, bytecode bytes:',c.evm.bytecode.object.length/2);
