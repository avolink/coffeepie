'use strict';
import { Process, Tasks, Logger, File } from 'runtime';

const executablePath = Process.findExecutable('x2goclient');

if (!executablePath) {
    Logger.error('No X2GO client (x2goclient) found on system');
    throw new Error(
        '<p>You must have installed latest X2GO Client in order to connect to this UDS service.</p>\n<p>Please, install the required packages for your platform</p>'
    );
}
Logger.info(`Using X2GO client at ${executablePath}`);

Logger.info(
    `Tunnel data: host=${data.tunnel.host}, port=${data.tunnel.port}, ticket=${data.tunnel.ticket}, verify_ssl=${data.tunnel.verify_ssl}, timeout=${data.tunnel.timeout}`,
);

const tunnel = await Tasks.startTunnel({
    addr: data.tunnel.host,
    port: data.tunnel.port,
    ticket: data.tunnel.ticket,
    startup_time_ms: data.tunnel.startup_time,
    check_certificate: data.tunnel.verify_ssl,
    shared_secret: data.shared_secret,
});

const keyFile = File.createTempFile(File.getHomeDirectory(), data.key, '.key');
Tasks.addEarlyUnlinkableFile(keyFile);

const home = File.getHomeDirectory() + ':1;/media:1;';
const sessionConf = data.xf
    .replace('{export}', home)
    .replace('{keyFile}', keyFile.replace(/\\/g, '/'))
    .replace('{ip}', '127.0.0.1')
    .replace('{port}', String(tunnel.port));

const sessionFile = File.createTempFile(File.getHomeDirectory(), sessionConf, '.conf');
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
Logger.info(`Created X2GO process with PID ${process}`);
Tasks.addWaitableApp(process);
