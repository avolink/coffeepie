'use strict';
import { Process, Tasks, Logger, File } from 'runtime';

// We receive data in "data" variable, which is an object from json readonly

const errorString = `<p>You must have installed latest X2GO Client in order to connect to this UDS service.</p>
<p>You can download it for windows from <a href="http://wiki.x2go.org/doku.php">X2Go Site</a>.</p>`;

// Find x2goclient.exe in the default installation path
const executablePath = Process.findExecutable('x2goclient.exe', [
    'C:\\Program Files (x86)\\x2goclient',
    'C:\\Program Files\\x2goclient',
]);

if (!executablePath) {
    Logger.error('No X2GO client (x2goclient.exe) found on system');
    throw new Error(errorString);
}

const keyFile = File.createTempFile(null, data.key, '.key');

const sessionConf = data.xf
    .replace('{export}', 'c:\\\\#1;')
    .replace('{keyFile}', keyFile.replace(/\\/g, '/'))
    .replace('{ip}', data.ip)
    .replace('{port}', data.port);

const sessionFile = File.createTempFile(null, sessionConf, '.conf');
Tasks.addEarlyUnlinkableFile(sessionFile);

Logger.debug(`Launching x2goclient: ${executablePath}`);
const process = Process.launch(executablePath, [
    `--session-conf=${sessionFile}`,
    '--session=UDS/connect',
    '--close-disconnect',
    '--hide',
    '--no-menu',
    '--add-to-known-hosts',
]);
Tasks.addWaitableApp(process);
