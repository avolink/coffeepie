const fs = require('fs');
const content = fs.readFileSync('tpe-optomechanical-switches-by-coffee-pie.html', 'utf-8');
const m = content.match(/id="avo-warmup-data">([\s\S]*?)<\/script>/);
if (m) {
    const data = JSON.parse(m[1]);
    const p = data.appsWarmupData['a0c68605-c2e7-4c8d-9ea1-767f9770e087']['tpe-optomechanical-switches-by-coffee-pie'].product;
    let out = "Items count: " + p.productItems.length + "\n";
    p.productItems.forEach(item => {
        out += `ID: ${item.id}\n  Options: ${JSON.stringify(item.optionsSelections)}\n  Visible: ${item.isVisible}\n  Inventory: ${JSON.stringify(item.inventory)}\n`;
    });
    fs.writeFileSync('out.txt', out);
}
