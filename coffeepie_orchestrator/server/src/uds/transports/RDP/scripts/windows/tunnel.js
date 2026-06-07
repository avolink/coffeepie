'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// Try, in order of preference, to find other RDP clients
const mstscPath = Process.findExecutable('mstsc.exe', ['C:\\Windows\\System32', 'C:\\Windows\\SysWOW64']);

if (!mstscPath) {
    Logger.error('No RDP client found on system');
    throw new Error('Unable to find mstsc.exe.');
}
Logger.info(`Using RDP client at ${mstscPath}`);

let password = '';
try {
    password = Utils.cryptProtectData(data.password);
} catch (e) {
    Logger.info('Could not encrypt password via DPAPI, user will be prompted: ' + e);
}

try {
    Utils.writeHkcuDword('Software\\Microsoft\\Terminal Server Client\\LocalDevices', '127.0.0.1', 255);
} catch (e) {
    Logger.info('Could not write registry key for device redirection: ' + e);
}

Logger.info(
    `Tunnel data: host=${data.tunnel.host}, port=${data.tunnel.port}, ticket=${data.tunnel.ticket}, verify_ssl=${data.tunnel.verify_ssl}, timeout=${data.tunnel.timeout}`,
);

const tunnel = await Tasks.startTunnel({
    addr: data.tunnel.host,
    port: data.tunnel.port,
    ticket: data.tunnel.ticket,
    startup_time_ms: data.tunnel.startup_time,
    check_certificate: data.tunnel.verify_ssl,
    shared_secret: data.shared_secret
});

let content = data.as_file.replace(/\{password\}/g, password);
content = content.replace(/\{address\}/g, `127.0.0.1:${tunnel.port}`);

let rdpFilePath = File.createTempFile(null, content, '.rdp');
Logger.info(`Created temporary RDP file at ${rdpFilePath}`);

let process = Process.launch(mstscPath, [rdpFilePath]);
Logger.info(`Created RDP process with PID ${process}`);

Tasks.addEarlyUnlinkableFile(rdpFilePath);
Logger.info(`Added early unlinkable file: ${rdpFilePath}`);
Tasks.addWaitableApp(process);
Logger.info(`Launched RDP client with file ${rdpFilePath}`);
