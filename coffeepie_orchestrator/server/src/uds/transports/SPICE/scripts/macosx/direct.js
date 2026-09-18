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

const spiceFilePath = File.createTempFile(File.getHomeDirectory(), data.as_file, '.vv');
Logger.debug(`SPICE temp file created at ${spiceFilePath}`);

Tasks.addEarlyUnlinkableFile(spiceFilePath);

Logger.debug(`Launching SPICE client (${remoteViewer}) with ${spiceFilePath}`);
const process = Process.launch(remoteViewer, [spiceFilePath]);
Tasks.addWaitableApp(process);
