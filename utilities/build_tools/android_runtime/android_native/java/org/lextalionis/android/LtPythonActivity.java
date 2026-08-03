package org.lextalionis.android;

import android.os.Bundle;

import org.kivy.android.PythonActivity;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;


/**
 * Keeps player data outside python-for-android's replaceable app directory.
 *
 * PythonActivity deletes filesDir/app when the packaged private payload
 * changes.  Move the legacy saves directory before PythonActivity gets a
 * chance to perform that cleanup.
 */
public final class LtPythonActivity extends PythonActivity {
    private static final String TAG = "LtPythonActivity";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        migrateLegacySaves();
        super.onCreate(savedInstanceState);
    }

    private void migrateLegacySaves() {
        File filesDir = getFilesDir();
        File legacySaves = new File(new File(filesDir, "app"), "saves");
        File userDataDir = new File(filesDir, "user_data");
        File persistentSaves = new File(userDataDir, "saves");

        if (persistentSaves.exists()) {
            if (!persistentSaves.isDirectory()) {
                throw new IllegalStateException(
                        "Persistent save path is not a directory: "
                                + persistentSaves.getAbsolutePath());
            }
            android.util.Log.i(
                    TAG,
                    "Persistent player data already exists; legacy saves remain untouched");
            return;
        }

        if (!legacySaves.exists()) {
            if (!userDataDir.exists() && !userDataDir.mkdirs()) {
                throw new IllegalStateException(
                        "Could not create persistent data directory: "
                                + userDataDir.getAbsolutePath());
            }
            if (!persistentSaves.mkdirs() && !persistentSaves.isDirectory()) {
                throw new IllegalStateException(
                        "Could not create persistent save directory: "
                                + persistentSaves.getAbsolutePath());
            }
            return;
        }

        if (!legacySaves.isDirectory()) {
            throw new IllegalStateException(
                    "Legacy save path is not a directory: "
                            + legacySaves.getAbsolutePath());
        }
        if (!userDataDir.exists() && !userDataDir.mkdirs()) {
            throw new IllegalStateException(
                    "Could not create persistent data directory: "
                            + userDataDir.getAbsolutePath());
        }

        try {
            // Both paths are siblings under getFilesDir(), so an atomic rename
            // is required.  A non-atomic fallback could leave no complete copy
            // just before PythonActivity removes filesDir/app.
            Files.move(
                    legacySaves.toPath(),
                    persistentSaves.toPath(),
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException | SecurityException error) {
            android.util.Log.e(TAG, "Could not migrate legacy saves", error);
            throw new IllegalStateException(
                    "Could not migrate legacy saves before APK update", error);
        }

        if (!persistentSaves.isDirectory()) {
            throw new IllegalStateException(
                    "Legacy save migration did not produce a directory: "
                            + persistentSaves.getAbsolutePath());
        }
    }
}
