import multiprocessing


def _inspect(connection, sources):
    import pymupdf

    results = []
    for source in sources:
        try:
            with pymupdf.open(source["path"]) as doc:
                encrypted = bool(doc.needs_pass or (doc.metadata or {}).get("encryption"))
                auth = doc.authenticate(source["password"])
                results.append({"name": source["name"], "encrypted": encrypted,
                                "readable": bool(auth), "owner": auth in {4, 6},
                                "can_decrypt": not encrypted or auth in {4, 6},
                                "pages": doc.page_count if auth else None})
        except Exception as exc:
            results.append({"name": source["name"], "error": str(exc)[:300]})
    connection.send(results)
    connection.close()


def inspect_documents(sources):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_inspect, args=(child, sources), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(60):
            raise ValueError("DOCUMENT_INSPECTION_TIMEOUT")
        return parent.recv()
    finally:
        parent.close()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
