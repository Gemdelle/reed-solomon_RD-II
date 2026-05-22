from pydantic import BaseModel


class FileMetadata(BaseModel):
    file_id: str
    filename: str
    sha256: str
    size: int
    created_at: str
