'use strict';
import { Tasks, Logger, RDP } from 'runtime';

Logger.info(`Tunnel data: host=${data.tunnel.host}, port=${data.tunnel.port}, ticket=${data.tunnel.ticket}, timeout=${data.tunnel.timeout}`);


const tunnel = await Tasks.startTunnel({
    addr: data.tunnel.host,
    port: data.tunnel.port,
    ticket: data.tunnel.ticket,
    startup_time_ms: data.tunnel.startup_time,
    shared_secret: data.shared_secret
});

data.port = tunnel.port;
data.server = '127.0.0.1';
Logger.info(`Tunnel established on port ${data.port}`);

RDP.start(data);