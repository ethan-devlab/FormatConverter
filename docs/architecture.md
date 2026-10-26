# Architecture and operational contracts

The browser communicates with one FastAPI process over loopback. There is no
cloud conversion service. Vite is used only during development; the portable
service serves the built static UI. Fluent UI supplies accessible controls;
TanStack Virtual limits mounted directory and queue rows; dnd-kit handles queue
ordering with keyboard and pointer controls. Native file drags use a scoped
workspace payload; browser file uploads stream to session-owned storage.

## Service boundaries

Host and Origin checks reject remote origins and DNS-rebinding hostnames. A
random session cookie is HttpOnly and SameSite Strict. Mutations require a
custom header, except the same-origin lifecycle beacon. No permissive CORS,
public listener, API documentation endpoint or request access log is enabled.
This is a single-user local service, not a multi-user authentication system.
Session cookie names include the web UI port so two local instances do not
replace each other's credential. This prevents accidental cookie collisions;
browser cookies still share a host across ports and this is not port isolation.

All supplied paths resolve inside user-added roots or the active temporary
session. Symbolic links and junction components are rejected. Root removal
withdraws later access. Inputs are fingerprinted before work, after work and
before a preview commit. These checks detect ordinary source changes; they are
not a filesystem transaction against a hostile local process.

## Work scheduling and memory

Text-to-PDF Markdown rendering runs a selected installed browser with a unique
task-owned profile. A token-scoped loopback server serves only generated HTML
and bundled offline assets. CSP blocks document network images, connections and
source scripts. Image bytes are embedded after registered-root and link checks;
their fingerprints are checked again before Preview commit. Recoverable image
issues are task warnings; parsing, math, diagram and engine errors fail the task.
Browser control uses CDP for Edge/Chrome and WebDriver BiDi for Firefox. No
browser binaries or automatic browser downloads are included. Safari product
integration and further user validation are pending; research is not product support.
Browser cleanup matches exact generated profile arguments because some browsers
relaunch outside the worker ancestry. Cancellation performs that cleanup before
terminating the worker. It does not terminate unrelated browser profiles.

The scheduler uses spawned worker processes with independent native PDF state.
One task occupies one worker. Images-to-PDF and merge preserve source order in
one aggregate task; independent files in the other tools run concurrently.
Workers are reused. The configured process count and observed RSS constrain new
starts. Native operations can temporarily exceed the memory budget; the budget
is not a hard operating-system memory limit. Cancellation terminates an active
worker and removes that task's staging data. Completed outputs remain available.

Jobs, source credentials, clipboard state and artifact registries live in memory.
Only preferences persist. Final output is staged in its destination filesystem,
flushed, then atomically published. Rename mode never overwrites an existing
name: Windows uses an atomic no-overwrite rename; other platforms use a hard link. Errors are per task; failed/cancelled items can be resubmitted.

## Directory events

watchfiles subscribes recursively to user-added roots. Events invalidate only
affected directory cache entries and are streamed to the browser with SSE.
Children are requested on expansion in pages of 200. Cached listings have a
30-second expiry, at most 64 directories and 100,000 metadata entries. The event
ring retains 1,024 entries; clients that fall behind request a rescan. Refresh
is explicit. A large single directory still requires one cold enumeration and
sort; the API thread performs it without blocking conversion workers.

File mutations use a separate operation lock to serialize clipboard and name
allocation, without holding the directory cache lock during a copy. Native
watcher updates and explicit invalidation both update the tree.

Overlapping roots use minimal native recursive subscriptions. Directory scans
do not publish a cache after an intervening invalidation. Directory responses
carry a snapshot version. The browser cancels superseded requests and rebuilds
loaded pages when an offset refers to an older version. Filtering runs before
pagination. Only visible expanded folders reload; removed roots withdraw pending
requests and stale action destinations. Display keys include the workspace root,
while selection and operations use case-insensitive Windows path identities.

File mutations normalize selected ancestors/descendants. Root and ancestor
protection is checked both at selection time and again before a cut paste.
Copies stage in the destination filesystem and publish with Windows no-overwrite
rename. Each copied file is checked for source changes. Failed cut entries keep
their original fingerprints for retry. A cut paste to the same parent is a no-op.

## Preview lifecycle

A preview is a real conversion into task-owned staging. Artifact URLs use opaque
IDs; arbitrary paths are not downloadable. Additional PDF pages render through
isolated internal tasks. Page changes remove earlier viewer tasks. Parameters
or source changes mark a preview stale. An identical completed request commits
the generated bytes directly. Temporary artifact URLs stop working after
commit. Text previews show at most 100,000 characters; the saved text is complete.

## Module map

| Module | Responsibility |
| --- | --- |
| `src/App.tsx` | Workspace state, tool selection, settings, jobs and dialogs. |
| `src/FileTree.tsx`, `src/Queue.tsx` | Lazy virtual directory tree and ordered selection queue. |
| `src/Parameters.tsx`, `src/Preview.tsx` | Effective tool controls and temporary result viewer. |
| `server/format_converter/api.py` | Local session boundary, API, static assets and SSE. |
| `files.py` | Root authorization, metadata cache, native events and file operations. |
| `jobs.py` | Worker scheduling, source validation, publication and cleanup. |
| `conversion.py`, `schemas.py` | Native conversion behavior and typed parameter contracts. |
| `inspection.py`, `picker.py` | Short-lived isolated PDF inspection and native folder selection. |
| `__main__.py` | Browser launch, loopback service and last-client lifecycle. |

## Packaging and support limits

PyInstaller bundles the runtime, static assets, native codecs and OCR data.
Dependency notices and the matching application source accompany the local
portable build. No installer, startup registration or global runtime setup is
performed. The executable is unsigned. Public publishing and a complete native
source distribution bundle are separate release work. Windows x64 is the only
validated platform.
