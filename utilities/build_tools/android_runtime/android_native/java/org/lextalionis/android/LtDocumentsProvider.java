package org.lextalionis.android;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Locale;

/**
 * Exposes the app's private data directory through Android's Storage Access
 * Framework. The runtime lives under files/app, while platformdirs stores
 * logs under cache, so the provider must expose their common parent.
 */
public final class LtDocumentsProvider extends DocumentsProvider {
    private static final String ROOT_ID = "lt-data";
    private static final String ROOT_DOCUMENT_ID = "root";

    private static final String[] DEFAULT_ROOT_PROJECTION = new String[] {
        Root.COLUMN_ROOT_ID,
        Root.COLUMN_FLAGS,
        Root.COLUMN_TITLE,
        Root.COLUMN_SUMMARY,
        Root.COLUMN_DOCUMENT_ID,
        Root.COLUMN_MIME_TYPES,
        Root.COLUMN_AVAILABLE_BYTES
    };

    private static final String[] DEFAULT_DOCUMENT_PROJECTION = new String[] {
        Document.COLUMN_DOCUMENT_ID,
        Document.COLUMN_DISPLAY_NAME,
        Document.COLUMN_MIME_TYPE,
        Document.COLUMN_FLAGS,
        Document.COLUMN_SIZE,
        Document.COLUMN_LAST_MODIFIED
    };

    private File rootDirectory;

    @Override
    public boolean onCreate() {
        rootDirectory = getContext().getFilesDir().getParentFile();
        if (rootDirectory == null) {
            return false;
        }
        return rootDirectory.isDirectory() || rootDirectory.mkdirs();
    }

    @Override
    public Cursor queryRoots(String[] projection) throws FileNotFoundException {
        MatrixCursor result = new MatrixCursor(
            projection != null ? projection : DEFAULT_ROOT_PROJECTION
        );
        MatrixCursor.RowBuilder row = result.newRow();
        addColumn(row, Root.COLUMN_ROOT_ID, ROOT_ID);
        addColumn(
            row,
            Root.COLUMN_FLAGS,
            Root.FLAG_LOCAL_ONLY | Root.FLAG_SUPPORTS_CREATE | Root.FLAG_SUPPORTS_IS_CHILD
        );
        addColumn(row, Root.COLUMN_TITLE, "Lex Talionis");
        addColumn(row, Root.COLUMN_SUMMARY, "Game files, saves, cache, and crash logs");
        addColumn(row, Root.COLUMN_DOCUMENT_ID, ROOT_DOCUMENT_ID);
        addColumn(row, Root.COLUMN_MIME_TYPES, "*/*");
        addColumn(row, Root.COLUMN_AVAILABLE_BYTES, rootDirectory.getUsableSpace());
        return result;
    }

    @Override
    public Cursor queryDocument(String documentId, String[] projection)
            throws FileNotFoundException {
        MatrixCursor result = new MatrixCursor(
            projection != null ? projection : DEFAULT_DOCUMENT_PROJECTION
        );
        includeFile(result, documentId, fileForDocumentId(documentId));
        return result;
    }

    @Override
    public Cursor queryChildDocuments(
            String parentDocumentId,
            String[] projection,
            String sortOrder) throws FileNotFoundException {
        File parent = fileForDocumentId(parentDocumentId);
        if (!parent.isDirectory()) {
            throw new FileNotFoundException("Not a directory: " + parentDocumentId);
        }
        MatrixCursor result = new MatrixCursor(
            projection != null ? projection : DEFAULT_DOCUMENT_PROJECTION
        );
        File[] children = parent.listFiles();
        if (children != null) {
            for (File child : children) {
                includeFile(result, documentIdForFile(child), child);
            }
        }
        return result;
    }

    @Override
    public ParcelFileDescriptor openDocument(
            String documentId,
            String mode,
            CancellationSignal signal) throws FileNotFoundException {
        File file = fileForDocumentId(documentId);
        if (!file.isFile()) {
            throw new FileNotFoundException("Not a file: " + documentId);
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.parseMode(mode));
    }

    @Override
    public String createDocument(String parentDocumentId, String mimeType, String displayName)
            throws FileNotFoundException {
        File parent = fileForDocumentId(parentDocumentId);
        if (!parent.isDirectory()) {
            throw new FileNotFoundException("Not a directory: " + parentDocumentId);
        }
        File child = safeChild(parent, displayName);
        try {
            boolean created = Document.MIME_TYPE_DIR.equals(mimeType)
                ? child.mkdir()
                : child.createNewFile();
            if (!created) {
                throw new IOException("Path already exists");
            }
            return documentIdForFile(child);
        } catch (IOException exc) {
            throw fileError("Could not create " + displayName, exc);
        }
    }

    @Override
    public void deleteDocument(String documentId) throws FileNotFoundException {
        if (ROOT_DOCUMENT_ID.equals(documentId) || isProtectedTopLevel(documentId)) {
            throw new FileNotFoundException(
                "The provider root and app data directories cannot be deleted"
            );
        }
        File file = fileForDocumentId(documentId);
        if (!deleteRecursively(file)) {
            throw new FileNotFoundException("Could not delete " + documentId);
        }
    }

    @Override
    public String renameDocument(String documentId, String displayName)
            throws FileNotFoundException {
        if (ROOT_DOCUMENT_ID.equals(documentId) || isProtectedTopLevel(documentId)) {
            throw new FileNotFoundException(
                "The provider root and app data directories cannot be renamed"
            );
        }
        File source = fileForDocumentId(documentId);
        File target = safeChild(source.getParentFile(), displayName);
        if (target.exists() || !source.renameTo(target)) {
            throw new FileNotFoundException("Could not rename " + documentId);
        }
        return documentIdForFile(target);
    }

    @Override
    public boolean isChildDocument(String parentDocumentId, String documentId) {
        try {
            File parent = fileForDocumentId(parentDocumentId);
            File child = fileForDocumentId(documentId);
            String parentPath = parent.getCanonicalPath();
            String childPath = child.getCanonicalPath();
            return childPath.equals(parentPath)
                || childPath.startsWith(parentPath + File.separator);
        } catch (IOException exc) {
            return false;
        }
    }

    private void includeFile(MatrixCursor result, String documentId, File file) {
        MatrixCursor.RowBuilder row = result.newRow();
        boolean directory = file.isDirectory();
        boolean isRoot = ROOT_DOCUMENT_ID.equals(documentId);
        int flags = isRoot || isProtectedTopLevel(documentId)
            ? 0
            : Document.FLAG_SUPPORTS_DELETE | Document.FLAG_SUPPORTS_RENAME;
        if (directory) {
            flags |= Document.FLAG_DIR_SUPPORTS_CREATE;
        } else if (file.canWrite()) {
            flags |= Document.FLAG_SUPPORTS_WRITE;
        }
        addColumn(row, Document.COLUMN_DOCUMENT_ID, documentId);
        addColumn(
            row,
            Document.COLUMN_DISPLAY_NAME,
            ROOT_DOCUMENT_ID.equals(documentId) ? "App Data" : file.getName()
        );
        addColumn(
            row,
            Document.COLUMN_MIME_TYPE,
            directory ? Document.MIME_TYPE_DIR : mimeTypeForFile(file)
        );
        addColumn(row, Document.COLUMN_FLAGS, flags);
        addColumn(row, Document.COLUMN_SIZE, directory ? null : file.length());
        addColumn(row, Document.COLUMN_LAST_MODIFIED, file.lastModified());
    }

    private static void addColumn(MatrixCursor.RowBuilder row, String column, Object value) {
        row.add(column, value);
    }

    private File fileForDocumentId(String documentId) throws FileNotFoundException {
        try {
            File root = rootDirectory.getCanonicalFile();
            File candidate;
            if (ROOT_DOCUMENT_ID.equals(documentId)) {
                candidate = root;
            } else if (documentId.startsWith(ROOT_DOCUMENT_ID + "/")) {
                candidate = new File(root, documentId.substring(ROOT_DOCUMENT_ID.length() + 1))
                    .getCanonicalFile();
            } else {
                throw new FileNotFoundException("Unknown document: " + documentId);
            }
            ensureInsideRoot(root, candidate);
            return candidate;
        } catch (IOException exc) {
            throw fileError("Invalid document " + documentId, exc);
        }
    }

    private String documentIdForFile(File file) throws FileNotFoundException {
        try {
            File root = rootDirectory.getCanonicalFile();
            File candidate = file.getCanonicalFile();
            ensureInsideRoot(root, candidate);
            String rootPath = root.getPath();
            String candidatePath = candidate.getPath();
            if (candidatePath.equals(rootPath)) {
                return ROOT_DOCUMENT_ID;
            }
            return ROOT_DOCUMENT_ID + "/"
                + candidatePath.substring(rootPath.length() + 1).replace(File.separatorChar, '/');
        } catch (IOException exc) {
            throw fileError("Could not resolve document", exc);
        }
    }

    private File safeChild(File parent, String displayName) throws FileNotFoundException {
        if (displayName == null || displayName.isEmpty()
                || displayName.equals(".") || displayName.equals("..")
                || displayName.contains("/") || displayName.contains("\\")) {
            throw new FileNotFoundException("Invalid display name");
        }
        try {
            File root = rootDirectory.getCanonicalFile();
            File child = new File(parent, displayName).getCanonicalFile();
            ensureInsideRoot(root, child);
            return child;
        } catch (IOException exc) {
            throw fileError("Invalid display name", exc);
        }
    }

    private static boolean isProtectedTopLevel(String documentId) {
        if (!documentId.startsWith(ROOT_DOCUMENT_ID + "/")) {
            return false;
        }
        String relative = documentId.substring(ROOT_DOCUMENT_ID.length() + 1);
        return !relative.isEmpty() && relative.indexOf('/') < 0;
    }

    private static void ensureInsideRoot(File root, File candidate)
            throws FileNotFoundException, IOException {
        String rootPath = root.getCanonicalPath();
        String candidatePath = candidate.getCanonicalPath();
        if (!candidatePath.equals(rootPath)
                && !candidatePath.startsWith(rootPath + File.separator)) {
            throw new FileNotFoundException("Document escapes provider root");
        }
    }

    private static boolean deleteRecursively(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children == null) {
                return false;
            }
            for (File child : children) {
                if (!deleteRecursively(child)) {
                    return false;
                }
            }
        }
        return file.delete();
    }

    private static String mimeTypeForFile(File file) {
        String name = file.getName();
        int dot = name.lastIndexOf('.');
        if (dot >= 0 && dot + 1 < name.length()) {
            String extension = name.substring(dot + 1).toLowerCase(Locale.ROOT);
            String mimeType = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
            if (mimeType != null) {
                return mimeType;
            }
        }
        return "application/octet-stream";
    }

    private static FileNotFoundException fileError(String message, Exception cause) {
        FileNotFoundException error = new FileNotFoundException(message);
        error.initCause(cause);
        return error;
    }
}
