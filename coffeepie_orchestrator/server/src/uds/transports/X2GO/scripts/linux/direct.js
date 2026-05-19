'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// Helper for debug logging types and existence
function logType(name, value) {
    let type = typeof value;
    let isFunction = type === 'function';
    let exists = value !== undefined && value !== null;
    Logger.debug(`[DEBUG] ${name}: type=${type}, isFunction=${isFunction}, exists=${exists}`);
}

// It is assumed that the data arrives in the variable "data" (readonly JSON object)

const errorString = `You must have installed latest X2GO Client in order to connect to this UDS service.\nPlease, install the required packages for your platform.`;

logType('Process.findExecutable', Process.findExecutable);
const executablePath = Process.findExecutable('x2goclient');
logType('executablePath', executablePath);

if (!executablePath) {
    Logger.error('No X2GO client found on system');
    throw new Error(errorString);
}

logType('File.createTempFile', File.createTempFile);
logType('File.getHomeDirectory', File.getHomeDirectory);
logType('data.key', data.key);
const keyFile = File.createTempFile(File.getHomeDirectory(), data.key, '.key');
logType('keyFile', keyFile);
logType('Tasks.addEarlyUnlinkableFile', Tasks.addEarlyUnlinkableFile);
Tasks.addEarlyUnlinkableFile(keyFile);

const home = File.getHomeDirectory() + ':1;/media:1;';
logType('data.xf', data.xf);
logType('Utils.expandVars', Utils.expandVars);
logType('keyFile.replace', keyFile.replace);
logType('data.ip', data.ip);
logType('data.port', data.port);
logType('data.login', data.login);
const sessionConf = Utils.expandVars(
    data.xf
        .replace('{export}', home)
        .replace('{keyFile}', keyFile.replace(/\\/g, '/'))
        .replace('{ip}', data.ip)
        .replace('{port}', data.port)
        .replace('{login}', data.login)
);
logType('sessionConf', sessionConf);

const sessionFile = File.createTempFile(File.getHomeDirectory(), sessionConf, '.conf');
logType('sessionFile', sessionFile);
Logger.debug('Session file created at: ' + sessionFile);
Tasks.addEarlyUnlinkableFile(sessionFile);

const params = [
    `--session-conf=${sessionFile}`,
    '--session=UDS/connect',
    '--close-disconnect',
    '--hide',
    '--no-menu',
    '--add-to-known-hosts',
];
logType('params', params);

logType('Process.launch', Process.launch);
const process = Process.launch(executablePath, params);
logType('process', process);
logType('Tasks.addWaitableApp', Tasks.addWaitableApp);
Tasks.addWaitableApp(process);
