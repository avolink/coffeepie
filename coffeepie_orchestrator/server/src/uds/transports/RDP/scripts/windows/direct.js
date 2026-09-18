'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// Try, in order of preference, to find other RDP clients
const mstscPath = Process.findExecutable('mstsc.exe', ['C:\\Windows\\System32', 'C:\\Windows\\SysWOW64']);

if (!mstscPath) {
    Logger.error('No RDP client found on system');
    throw new Error('Unable to find mstsc.exe.');
}

let password = '';
try {
    password = Utils.cryptProtectData(data.password);
} catch (e) {
    Logger.info('Could not encrypt password via DPAPI, user will be prompted: ' + e);
}

try {
    Utils.writeHkcuDword('Software\\Microsoft\\Terminal Server Client\\LocalDevices', data.ip, 255);
} catch (e) {
    Logger.info('Could not write registry key for device redirection: ' + e);
}

let content = data.as_file.replace(/\{password\}/g, password);
let rdpFilePath = File.createTempFile(null, content, '.rdp');
let process = Process.launch(mstscPath, [rdpFilePath]);
Tasks.addEarlyUnlinkableFile(rdpFilePath);
Tasks.addWaitableApp(process);
Logger.info(`Launched RDP client with file ${rdpFilePath}`);
