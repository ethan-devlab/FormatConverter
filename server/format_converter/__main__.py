from __future__ import annotations

import argparse
import multiprocessing
import threading
import time
import webbrowser


def main():
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--pick-folder", action="store_true")
    args = parser.parse_args()
    if args.pick_folder:
        from .picker import native_root
        from tkinter import filedialog
        with native_root() as root:
            value = filedialog.askdirectory(parent=root, title="Format Converter", mustexist=True)
        print(value, flush=True)
        return
    import uvicorn
    from .api import create_app
    app = create_app(dev=args.dev)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning", use_colors=False))

    def monitor():
        while not server.should_exit:
            time.sleep(1)
            if server.started and not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{args.port}")
                args.no_browser = True
            if args.dev:
                continue
            now = time.monotonic()
            for identity, last in list(app.state.clients.items()):
                if now - last > 180:
                    app.state.clients.pop(identity, None)
                    app.state.last_close = now
            if not app.state.clients and not app.state.manager.busy():
                if (app.state.had_clients and now - app.state.last_close > 30) or now - app.state.started > 180:
                    server.should_exit = True
    threading.Thread(target=monitor, daemon=True, name="client-lifecycle").start()
    server.run()


if __name__ == "__main__":
    main()
