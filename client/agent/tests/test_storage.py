from storage.store import FileStorage


def test_save_and_retrieve(tmp_storage):
    fs = FileStorage(tmp_storage)
    data = b"hello storage"
    meta = fs.save(data, "hello.txt")

    assert "file_id" in meta
    assert meta["filename"] == "hello.txt"
    assert meta["size"] == len(data)
    assert len(meta["sha256"]) == 64

    assert fs.get_bytes(meta["file_id"]) == data


def test_get_meta(tmp_storage):
    fs = FileStorage(tmp_storage)
    meta = fs.save(b"metadata content", "meta.bin")
    retrieved = fs.get_meta(meta["file_id"])
    assert retrieved is not None
    assert retrieved["file_id"] == meta["file_id"]
    assert retrieved["sha256"] == meta["sha256"]
    assert retrieved["size"] == 16


def test_list_all(tmp_storage):
    fs = FileStorage(tmp_storage)
    m1 = fs.save(b"file one", "a.txt")
    m2 = fs.save(b"file two", "b.txt")
    ids = {f["file_id"] for f in fs.list_all()}
    assert m1["file_id"] in ids
    assert m2["file_id"] in ids


def test_delete(tmp_storage):
    fs = FileStorage(tmp_storage)
    meta = fs.save(b"to be deleted", "bye.txt")
    file_id = meta["file_id"]

    assert fs.delete(file_id) is True
    assert fs.get_bytes(file_id) is None
    assert fs.get_meta(file_id) is None


def test_delete_nonexistent(tmp_storage):
    fs = FileStorage(tmp_storage)
    assert fs.delete("does-not-exist") is False


def test_missing_returns_none(tmp_storage):
    fs = FileStorage(tmp_storage)
    assert fs.get_bytes("ghost") is None
    assert fs.get_meta("ghost") is None


def test_filename_defaults_to_id_when_empty(tmp_storage):
    fs = FileStorage(tmp_storage)
    meta = fs.save(b"no name", "")
    assert meta["filename"] == meta["file_id"]
