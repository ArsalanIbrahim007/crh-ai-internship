import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Folder,
  Grid2X2,
  List,
  Plus,
  Search,
  Sheet,
  Presentation,
  Upload,
  ChevronRight,
} from "lucide-react";
import {
  ActionMenu,
  WorkspaceDialog,
} from "../components/workspace/WorkspaceControls";
import {
  createFolder,
  deleteDocument,
  deleteFolder,
  fileKind,
  fileSize,
  listDocuments,
  listFolders,
  moveDocument,
  renameFolder,
  uploadDocument,
  type WorkspaceFile,
  type WorkspaceFolder,
} from "../lib/workspace";
import "./workspace.css";
const categories = [
  ["pdf", "PDFs", FileText],
  ["document", "Documents", FileText],
  ["spreadsheet", "Spreadsheets", Sheet],
  ["slides", "Slides", Presentation],
  ["text", "Texts", FileText],
] as const;
type DialogState =
  | { kind: "create" }
  | { kind: "rename"; folder: WorkspaceFolder }
  | { kind: "delete-folder"; folder: WorkspaceFolder }
  | { kind: "file"; file: WorkspaceFile }
  | { kind: "delete-file"; file: WorkspaceFile };
function FileVisual({ name }: { name: string }) {
  const kind = fileKind(name);
  return (
    <span
      className={`documents-page__visual documents-page__visual--${kind}`}
      aria-hidden="true"
    >
      {kind === "spreadsheet" ? (
        <Sheet />
      ) : kind === "slides" ? (
        <Presentation />
      ) : (
        <FileText />
      )}
      <b>
        {kind === "pdf"
          ? "PDF"
          : kind === "spreadsheet"
            ? "XLS"
            : kind === "slides"
              ? "PPT"
              : kind === "text"
                ? "TXT"
                : "DOC"}
      </b>
    </span>
  );
}
export function DocumentsPage() {
  const [files, setFiles] = useState<WorkspaceFile[]>([]),
    [folders, setFolders] = useState<WorkspaceFolder[]>([]);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("all"),
    [folderId, setFolderId] = useState<string | null>(null);
  const [view, setView] = useState("grid"),
    [selected, setSelected] = useState<string[]>([]);
  const [dialog, setDialog] = useState<DialogState | null>(null),
    [name, setName] = useState(""),
    [dialogError, setDialogError] = useState("");
  const [pending, setPending] = useState(false),
    [uploading, setUploading] = useState(false),
    [notice, setNotice] = useState(""),
    [uploadError, setUploadError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null),
    uploadTarget = useRef<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    Promise.all([
      listDocuments(controller.signal),
      listFolders(controller.signal),
    ])
      .then(([documents, directories]) => {
        setFiles(documents);
        setFolders(directories);
        setFolderId((current) =>
          current && !directories.some((folder) => folder.folder_id === current)
            ? null
            : current,
        );
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  const activeFolder = folders.find((folder) => folder.folder_id === folderId);
  const scoped = files.filter(
    (file) => !folderId || file.folder_id === folderId,
  );
  const visible = scoped.filter(
    (file) =>
      (category === "all" || fileKind(file.filename) === category) &&
      file.filename.toLowerCase().includes(query.toLowerCase()),
  );
  const visibleFolders =
    !folderId && category === "all"
      ? folders.filter((folder) =>
          folder.name.toLowerCase().includes(query.toLowerCase()),
        )
      : [];
  function openFolder(folder: WorkspaceFolder) {
    setFolderId(folder.folder_id);
    setCategory("all");
    setQuery("");
  }
  function showDialog(next: DialogState) {
    setDialogError("");
    setName(next.kind === "rename" ? next.folder.name : "");
    setDialog(next);
  }
  function chooseUpload(target = folderId) {
    uploadTarget.current = target;
    fileInput.current?.click();
  }
  async function upload(file: File) {
    setUploading(true);
    setUploadError("");
    try {
      await uploadDocument(file, uploadTarget.current, setNotice);
      setNotice(`Uploaded ${file.name}`);
      setRevision((value) => value + 1);
    } catch (error) {
      setUploadError((error as Error).message);
      setNotice("");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  async function submitDialog() {
    if (!dialog) return;
    setPending(true);
    setDialogError("");
    try {
      if (dialog.kind === "create") await createFolder(name.trim());
      if (dialog.kind === "rename")
        await renameFolder(dialog.folder.folder_id, name.trim());
      if (dialog.kind === "delete-folder")
        await deleteFolder(dialog.folder.folder_id);
      if (dialog.kind === "delete-file") await deleteDocument(dialog.file.id);
      setDialog(null);
      setRevision((value) => value + 1);
    } catch (error) {
      setDialogError((error as Error).message);
    } finally {
      setPending(false);
    }
  }
  const dialogTitle = !dialog
    ? ""
    : dialog.kind === "create"
      ? "Create folder"
      : dialog.kind === "rename"
        ? "Rename folder"
        : dialog.kind === "delete-folder"
          ? `Delete “${dialog.folder.name}”?`
          : dialog.kind === "delete-file"
            ? `Delete “${dialog.file.filename}”?`
            : dialog.file.filename;
  return (
    <main className="workspace-page documents-page">
      <div className="workspace-page__surface">
        <header className="workspace-page__header">
          <div>
            <h1>Documents</h1>
            <p>Search, analyze and organize your business knowledge.</p>
          </div>
          <button
            className="workspace-page__button workspace-page__button--primary"
            disabled={uploading || loading || Boolean(error)}
            onClick={() => chooseUpload()}
          >
            <Upload size={18} />
            {uploading ? notice : "Upload document"}
          </button>
          <input
            ref={fileInput}
            type="file"
            hidden
            accept=".pdf,.docx,.csv,.xlsx,.xlsm,.txt,.md,.html"
            aria-label="Choose document to upload"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
            }}
          />
        </header>
        <div className="documents-page__toolbar">
          <div className="documents-page__breadcrumb">
            <button
              onClick={() => {
                setFolderId(null);
                setCategory("all");
              }}
            >
              Documents
            </button>
            {activeFolder && (
              <>
                <ChevronRight size={16} />
                <span>{activeFolder.name}</span>
              </>
            )}
          </div>
          <div className="documents-page__tools">
            <label className="documents-page__search">
              <Search size={19} />
              <input
                aria-label="Search documents"
                placeholder="Search documents..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="documents-page__view" aria-label="File view">
              <button
                aria-label="Grid view"
                aria-pressed={view === "grid"}
                className={view === "grid" ? "is-active" : ""}
                onClick={() => setView("grid")}
              >
                <Grid2X2 size={20} />
              </button>
              <button
                aria-label="List view"
                aria-pressed={view === "list"}
                className={view === "list" ? "is-active" : ""}
                onClick={() => setView("list")}
              >
                <List size={20} />
              </button>
            </div>
          </div>
        </div>
        {(notice || uploadError) && (
          <p
            className="workspace-page__notice"
            role={uploadError ? "alert" : "status"}
          >
            {uploadError || notice}
          </p>
        )}
        <div className="documents-page__layout">
          <aside
            className="documents-page__categories workspace-scroll"
            aria-label="Categories and folders"
          >
            <h2>File categories</h2>
            <button
              className={category === "all" ? "is-active" : ""}
              aria-pressed={category === "all"}
              onClick={() => setCategory("all")}
            >
              <FileText size={20} />
              <span>All files</span>
              {scoped.length > 0 && <small>{scoped.length}</small>}
            </button>
            {categories.map(([key, label, Icon]) => {
              const count = scoped.filter(
                (file) => fileKind(file.filename) === key,
              ).length;
              return (
                count > 0 && (
                  <button
                    key={key}
                    className={category === key ? "is-active" : ""}
                    aria-pressed={category === key}
                    onClick={() => setCategory(key)}
                  >
                    <Icon size={20} />
                    <span>{label}</span>
                    <small>{count}</small>
                  </button>
                )
              );
            })}
            <div className="documents-page__folder-heading">
              <h2>Folders</h2>
              <button
                aria-label="Create folder"
                disabled={loading || Boolean(error)}
                onClick={() => showDialog({ kind: "create" })}
              >
                <Plus size={20} />
              </button>
            </div>
            {folders.map((folder) => (
              <div
                className={`documents-page__folder-nav ${folderId === folder.folder_id ? "is-active" : ""}`}
                key={folder.folder_id}
              >
                <button onClick={() => openFolder(folder)}>
                  <Folder size={19} />
                  <span>{folder.name}</span>
                </button>
                <ActionMenu label={`Actions for folder ${folder.name}`}>
                  <button onClick={() => openFolder(folder)}>Open</button>
                  <button
                    onClick={() => showDialog({ kind: "rename", folder })}
                  >
                    Rename
                  </button>
                  <button
                    disabled={uploading}
                    onClick={() => chooseUpload(folder.folder_id)}
                  >
                    Upload document
                  </button>
                  <button
                    onClick={() =>
                      showDialog({ kind: "delete-folder", folder })
                    }
                  >
                    Delete folder
                  </button>
                </ActionMenu>
              </div>
            ))}
          </aside>
          <section
            className="documents-page__results workspace-scroll"
            aria-label="Document results"
            aria-busy={loading}
          >
            {loading ? (
              <div
                className="documents-page__grid"
                role="status"
                aria-label="Loading documents"
              >
                {Array.from({ length: 6 }, (_, index) => (
                  <div key={index} className="documents-page__skeleton" />
                ))}
              </div>
            ) : error ? (
              <div className="workspace-page__empty" role="alert">
                <h2>Couldn’t load documents</h2>
                <p>{error}</p>
                <button
                  className="workspace-page__button"
                  onClick={() => setRevision((value) => value + 1)}
                >
                  Retry
                </button>
              </div>
            ) : (
              <>
                <div className={`documents-page__${view}`}>
                  {visibleFolders.map((folder) => (
                    <article
                      className="documents-page__card documents-page__folder-card"
                      key={folder.folder_id}
                    >
                      <button
                        className="documents-page__file-select"
                        onClick={() => openFolder(folder)}
                      >
                        <Folder className="documents-page__folder-visual" />
                        <strong>{folder.name}</strong>
                        {folder.document_count > 0 && (
                          <span>{folder.document_count} documents</span>
                        )}
                      </button>
                      <ActionMenu
                        label={`Folder card actions for ${folder.name}`}
                      >
                        <button onClick={() => openFolder(folder)}>Open</button>
                        <button
                          onClick={() => showDialog({ kind: "rename", folder })}
                        >
                          Rename
                        </button>
                        <button
                          disabled={uploading}
                          onClick={() => chooseUpload(folder.folder_id)}
                        >
                          Upload document
                        </button>
                        <button
                          onClick={() =>
                            showDialog({ kind: "delete-folder", folder })
                          }
                        >
                          Delete folder
                        </button>
                      </ActionMenu>
                    </article>
                  ))}
                  {visible.map((file) => (
                    <article
                      className={`documents-page__card ${selected.includes(file.id) ? "is-selected" : ""}`}
                      key={file.id}
                    >
                      <button
                        className="documents-page__file-select"
                        aria-pressed={selected.includes(file.id)}
                        onClick={() =>
                          setSelected((current) =>
                            current.includes(file.id)
                              ? current.filter((id) => id !== file.id)
                              : [...current, file.id],
                          )
                        }
                      >
                        <FileVisual name={file.filename} />
                        <strong title={file.filename}>{file.filename}</strong>
                        <span>
                          {fileKind(file.filename)} · {fileSize(file.size)}
                        </span>
                        <time dateTime={file.updated_at}>
                          {new Date(
                            file.updated_at ?? file.created_at,
                          ).toLocaleDateString()}
                        </time>
                      </button>
                      <ActionMenu
                        label={`Actions for document ${file.filename}`}
                      >
                        <button
                          onClick={() => showDialog({ kind: "file", file })}
                        >
                          Details / move
                        </button>
                        <button
                          onClick={() =>
                            showDialog({ kind: "delete-file", file })
                          }
                        >
                          Delete document
                        </button>
                      </ActionMenu>
                    </article>
                  ))}
                </div>
                {!visible.length && !visibleFolders.length && (
                  <div className="workspace-page__empty">
                    <FileText size={42} />
                    <h2>
                      {query || category !== "all"
                        ? "No matching documents"
                        : "No documents yet"}
                    </h2>
                    <p>
                      {query || category !== "all"
                        ? "Try a different search or file category."
                        : "Upload your first document to search, analyze and use it with the AI."}
                    </p>
                    {!query && category === "all" && (
                      <button
                        className="workspace-page__button"
                        disabled={uploading}
                        onClick={() => chooseUpload()}
                      >
                        <Upload size={18} />
                        Upload document
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        </div>
        {dialog && (
          <WorkspaceDialog
            title={dialogTitle}
            close={() => {
              if (!pending) setDialog(null);
            }}
          >
            {dialog.kind === "file" ? (
              <>
                <p>
                  {dialog.file.mime_type} · {fileSize(dialog.file.size)}
                </p>
                <label className="workspace-dialog__field">
                  Move to folder
                  <select
                    disabled={pending}
                    defaultValue={dialog.file.folder_id ?? ""}
                    onChange={async (event) => {
                      setPending(true);
                      setDialogError("");
                      try {
                        await moveDocument(
                          dialog.file.id,
                          event.target.value || null,
                        );
                        setDialog(null);
                        setRevision((value) => value + 1);
                      } catch (error) {
                        setDialogError((error as Error).message);
                      } finally {
                        setPending(false);
                      }
                    }}
                  >
                    <option value="">Documents (no folder)</option>
                    {folders.map((folder) => (
                      <option key={folder.folder_id} value={folder.folder_id}>
                        {folder.name}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void submitDialog();
                }}
              >
                {dialog.kind === "create" || dialog.kind === "rename" ? (
                  <label className="workspace-dialog__field">
                    Folder name
                    <input
                      autoFocus
                      required
                      maxLength={120}
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </label>
                ) : dialog.kind === "delete-folder" ? (
                  <p>
                    This folder contains {dialog.folder.document_count}{" "}
                    documents.{" "}
                    {dialog.folder.document_count > 0
                      ? "Move or delete those documents first. Non-empty folders cannot be deleted."
                      : "The empty folder will be permanently deleted."}
                  </p>
                ) : (
                  <p>
                    This permanently deletes the document and its searchable
                    content. This action cannot be undone.
                  </p>
                )}
                <div className="workspace-dialog__actions">
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => setDialog(null)}
                  >
                    Cancel
                  </button>
                  <button
                    className="workspace-page__button"
                    disabled={
                      pending ||
                      (dialog.kind === "delete-folder" &&
                        dialog.folder.document_count > 0) ||
                      ((dialog.kind === "create" || dialog.kind === "rename") &&
                        !name.trim())
                    }
                  >
                    {pending
                      ? "Saving…"
                      : dialog.kind.startsWith("delete")
                        ? "Delete"
                        : "Save"}
                  </button>
                </div>
              </form>
            )}
            {dialogError && <p role="alert">{dialogError}</p>}
          </WorkspaceDialog>
        )}
      </div>
    </main>
  );
}
