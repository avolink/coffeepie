'use strict';
import { Process, Tasks, Logger, File } from 'runtime';

// We receive data in "data" variable, which is an object from json readonly

const remoteViewer = '/Applications/RemoteViewer.app/Contents/MacOS/RemoteViewer';

const errorString = `<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
<p><a href="https://ports.macports.org/port/virt-viewer/">Open download page</a></p>
<p>Please, note that in order to UDS Connector to work correctly, you must copy the Remote Viewer app to your Applications Folder.<br/>
Also remember, that in order to allow this app to run on your system, you must open it one time once it is copied to your App folder</p>`;

if (!File.exists(remoteViewer)) {
    Logger.error('No SPICE client (remote-viewer) found at: ' + remoteViewer);
    throw new Error(errorString);
}

let theFile = data.as_file_ns;
let fs = null;
let fss = null;

if (data.ticket) {
    fs = await Tasks.startTunnel(
        data.tunHost,
        parseInt(data.tunPort),
        data.ticket,
        data.tunWait,
        data.tunChk,
    );
    if (!fs) {
        throw new Error('<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>');
    }
}

if (data.ticket_secure) {
    theFile = data.as_file;
    fss = await Tasks.startTunnel(
        data.tunHost,
        parseInt(data.tunPort),
        data.ticket_secure,
        data.tunWait,
        data.tunChk,
    );
    if (!fss) {
        throw new Error('<p>Could not connect to tunnel server 2.</p><p>Please, check your network settings.</p>');
    }
}

theFile = theFile
    .replace('{secure_port}', fss ? fss.port : '-1')
    .replace('{port}', fs ? fs.port : '-1');

const filename = File.createTempFile(File.getHomeDirectory(), theFile, '.vv');
Tasks.addEarlyUnlinkableFile(filename);

Logger.debug(`Launching SPICE client (${remoteViewer}) with ${filename}`);
const process = Process.launch(remoteViewer, [filename]);
Tasks.addWaitableApp(process);
