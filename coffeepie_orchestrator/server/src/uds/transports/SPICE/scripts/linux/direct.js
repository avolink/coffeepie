'use strict';
import { Process, Tasks, Logger, File, Utils } from 'runtime';

// We receive data in "data" variable, which is an object from json readonly

const errorString = `You need to have virt-viewer (remote-viewer) installed and in path for this to work.\nPlease, install the proper package for your system.\nhttps://virt-manager.org/download/|* virt-viewer (remote-viewer)`;

// Try to find the remote-viewer executable
const executablePath = Process.findExecutable('remote-viewer');

if (!executablePath) {
    Logger.error('No SPICE client (remote-viewer) found on system');
    throw new Error(errorString);
}

// If has the as_file property, create the temp file on home folder and use it
if (data.as_file) {
    Logger.debug('Has file property, creating temp SPICE file');
    // Create and save the temp file
    let spiceFilePath = File.createTempFile(File.getHomeDirectory(), data.as_file, '.vv');
    Logger.debug(`SPICE temp file created at ${spiceFilePath}`);

    // Append to removable task to delete the file later
    Tasks.addEarlyUnlinkableFile(spiceFilePath);
    // Launch the SPICE client with the temp file
    Logger.debug(`Launching SPICE client (${executablePath}) with ${spiceFilePath}`);
    let process = Process.launch(executablePath, [spiceFilePath]);
    Tasks.addWaitableApp(process);
} else {
    Logger.error('No file property found in data for SPICE connection');
    throw new Error('SPICE connection requires a file property with the connection file content.');
}
