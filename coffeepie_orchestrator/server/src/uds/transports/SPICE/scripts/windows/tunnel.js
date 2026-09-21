'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// We receive data in "data" variable, which is an object from json readonly

const errorString = `<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
<p><a href="https://virt-manager.org/download">Open download page</a></p>`;

// Find remote-viewer.exe via Windows registry (.vvfile open command)
const regKey = 'HKEY_CLASSES_ROOT\\VirtViewer.vvfile\\shell\\open\\command';
let executablePath = null;
try {
    const command = Utils.readHkcr('VirtViewer.vvfile\\shell\\open\\command', '');
    Logger.debug(`Registry ${regKey} -> (Default): ${command}`);
    if (command) {
        // Command is like: "C:\Program Files\VirtViewer v11.0\bin\remote-viewer.exe" "%1"
        const match = command.match(/^"([^"]+)"/);
        const candidate = match ? match[1] : command.split(' ')[0];
        if (File.exists(candidate)) {
            executablePath = candidate;
        }
    }
} catch (e) {
    Logger.debug(`Registry ${regKey} not found: ${e}`);
}

// Fallback: scan VirtViewer* subdirs under Program Files
if (!executablePath) {
    for (const base of ['C:\\Program Files', 'C:\\Program Files (x86)']) {
        try {
            for (const entry of File.listDir(base)) {
                if (entry.startsWith('VirtViewer')) {
                    const candidate = `${base}\\${entry}\\bin\\remote-viewer.exe`;
                    if (File.exists(candidate)) {
                        executablePath = candidate;
                        break;
                    }
                }
            }
        } catch (_) {}
        if (executablePath) break;
    }
}

// Fallback: search PATH
if (!executablePath) {
    executablePath = Process.findExecutable('remote-viewer.exe');
}

if (!executablePath) {
    Logger.error('No SPICE client (remote-viewer.exe) found on system');
    throw new Error(errorString);
}

let theFile = data.as_file_ns;
let fs = null;
let fss = null;

if (data.ticket) {
    fs = await Tasks.startTunnel({
        addr: data.tunHost,
        port: data.tunPort,
        ticket: data.ticket,
        startup_time_ms: data.tunWait,
        check_certificate: data.tunChk,
    });
}

if (data.ticket_secure) {
    theFile = data.as_file;
    fss = await Tasks.startTunnel({
        addr: data.tunHost,
        port: data.tunPort,
        ticket: data.ticket_secure,
        startup_time_ms: data.tunWait,
        check_certificate: data.tunChk,
    });
}

theFile = theFile
    .replace('{secure_port}', fss ? fss.port : '-1')
    .replace('{port}', fs ? fs.port : '-1');

const spiceFilePath = File.createTempFile(File.getTempDirectory(), theFile, '.vv');
Tasks.addEarlyUnlinkableFile(spiceFilePath);

Logger.debug(`Launching SPICE client (${executablePath}) with ${spiceFilePath}`);
const process = Process.launch(executablePath, [spiceFilePath]);
Tasks.addWaitableApp(process);
