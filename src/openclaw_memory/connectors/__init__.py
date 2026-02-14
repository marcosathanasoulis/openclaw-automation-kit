from .base import ConnectorBatch, ConnectorProtocol, NormalizedRecord
from .json_file import JsonFileConnector

__all__ = ["ConnectorProtocol", "ConnectorBatch", "NormalizedRecord", "JsonFileConnector"]
