
'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// Recibimos los datos en la variable "data" (objeto JSON de solo lectura)

const errorString = `<p>You need to have installed virt-viewer to connect to this UDS service.</p>\n<p>Please, install appropriate package for your system.</p>\n<p>Please, install appropriate package for your Linux system. (probably named something like <b>virt-viewer</b>)</p>`;

// Buscar el ejecutable de remote-viewer
const executable = Process.findExecutable('remote-viewer');
if (!executable) {
    throw new Error(errorString);
}

let fs = null;
let fss = null;
let theFile = data.as_file_ns;

if (data.ticket) {
    // Abrir túnel
    fs = await Tasks.startTunnel(
        data.tunHost,
        parseInt(data.tunPort),
        data.ticket,
        data.tunWait,
        data.tunChk,
    );
    // Comprobar que el túnel funciona
    if (!fs) {
        throw new Error('<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>');
    }
}

if (data.ticket_secure) {
    // Abrir túnel seguro
    theFile = data.as_file;
    fss = await Tasks.startTunnel(
        data.tunHost,
        parseInt(data.tunPort),
        data.ticket_secure,
        data.tunWait,
        data.tunChk,
    );
    // Comprobar que el túnel seguro funciona
    if (!fss) {
        throw new Error('<p>Could not connect to tunnel server 2.</p><p>Please, check your network settings.</p>');
    }
}

// Formatear el archivo con los puertos de los túneles
theFile = theFile
    .replace('{secure_port}', fss ? fss.port : '-1')
    .replace('{port}', fs ? fs.port : '-1');

// Guardar archivo temporal y lanzar remote-viewer
const filename = File.createTempFile(File.getHomeDirectory(), theFile, '.vv');
Tasks.addEarlyUnlinkableFile(filename);
Logger.debug(`Launching SPICE client (${executable}) with ${filename}`);
const process = Process.launch(executable, [filename]);
Tasks.addWaitableApp(process);
