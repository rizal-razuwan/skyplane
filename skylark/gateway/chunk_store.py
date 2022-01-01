from multiprocessing import Manager
from os import PathLike
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from skylark.gateway.chunk import ChunkRequest, ChunkRequestHop, ChunkState


class ChunkStore:
    def __init__(self, chunk_dir: PathLike):
        self.chunk_dir = Path(chunk_dir)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)

        # delete existing chunks
        for chunk_file in self.chunk_dir.glob("*.chunk"):
            logger.warning(f"Deleting existing chunk file {chunk_file}")
            chunk_file.unlink()

        # multiprocess-safe concurrent structures
        self.manager = Manager()
        self.chunk_requests: Dict[int, ChunkRequest] = self.manager.dict()
        self.chunk_status: Dict[int, ChunkState] = self.manager.dict()

    def get_chunk_file_path(self, chunk_id: int) -> Path:
        return self.chunk_dir / f"{chunk_id}.chunk"

    ###
    # ChunkState management
    ###
    def get_chunk_state(self, chunk_id: int) -> Optional[ChunkState]:
        return self.chunk_status[chunk_id] if chunk_id in self.chunk_status else None

    def set_chunk_state(self, chunk_id: int, new_status: ChunkState):
        self.chunk_status[chunk_id] = new_status

    def state_start_download(self, chunk_id: int):
        state = self.get_chunk_state(chunk_id)
        if state in [ChunkState.registered, ChunkState.download_in_progress]:
            self.set_chunk_state(chunk_id, ChunkState.download_in_progress)
        else:
            raise ValueError(f"Invalid transition start_download from {self.get_chunk_state(chunk_id)}")

    def state_finish_download(self, chunk_id: int, runtime_s: Optional[float] = None):
        # todo log runtime to statistics store
        state = self.get_chunk_state(chunk_id)
        if state in [ChunkState.download_in_progress, ChunkState.downloaded]:
            self.set_chunk_state(chunk_id, ChunkState.downloaded)
        else:
            raise ValueError(f"Invalid transition finish_download from {self.get_chunk_state(chunk_id)}")

    def state_start_upload(self, chunk_id: int):
        state = self.get_chunk_state(chunk_id)
        if state in [ChunkState.downloaded, ChunkState.upload_in_progress]:
            self.set_chunk_state(chunk_id, ChunkState.upload_in_progress)
        else:
            raise ValueError(f"Invalid transition start_upload from {self.get_chunk_state(chunk_id)}")

    def state_finish_upload(self, chunk_id: int, runtime_s: Optional[float] = None):
        # todo log runtime to statistics store
        state = self.get_chunk_state(chunk_id)
        if state in [ChunkState.upload_in_progress, ChunkState.upload_complete]:
            self.set_chunk_state(chunk_id, ChunkState.upload_complete)
        else:
            raise ValueError(f"Invalid transition finish_upload from {self.get_chunk_state(chunk_id)}")

    def state_fail(self, chunk_id: int):
        if self.get_chunk_state(chunk_id) != ChunkState.upload_complete:
            self.set_chunk_state(chunk_id, ChunkState.failed)
        else:
            raise ValueError(f"Invalid transition fail from {self.get_chunk_state(chunk_id)}")

    ###
    # Chunk management
    ###
    def get_chunk_requests(self, status: Optional[ChunkState] = None) -> List[ChunkRequest]:
        if status is None:
            return list(self.chunk_requests.values())
        else:
            return [req for i, req in self.chunk_requests.items() if self.get_chunk_state(i) == status]

    def get_chunk_request(self, chunk_id: int) -> Optional[ChunkRequest]:
        return self.chunk_requests[chunk_id] if chunk_id in self.chunk_requests else None

    def add_chunk_request(self, chunk_request: ChunkRequest, state=ChunkState.registered):
        logger.debug(f"Adding chunk request {chunk_request.chunk.chunk_id}")
        self.set_chunk_state(chunk_request.chunk.chunk_id, state)
        self.chunk_requests[chunk_request.chunk.chunk_id] = chunk_request

    def pop_chunk_request_path(self, chunk_id: int) -> Optional[ChunkRequestHop]:
        if chunk_id in self.chunk_requests:
            chunk_request = self.chunk_requests[chunk_id]
            if len(chunk_request.path) > 0:
                result = chunk_request.path.pop(0)
                self.chunk_requests[chunk_id] = chunk_request
                return result
        return None