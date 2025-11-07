"""
xnat_pipelines v0.5.0
- full I/O staging + filters
- dual-mode exec (remote/local) with retries + batch
- schema-aware input mapping for local
- HTML dashboard for monitoring
"""
from .containers import ContainerClient, ContainerCommand
from .executor import Executor, JobHandle
from .batch import BatchRunner, BatchResult, QueueEvent

__all__ = ["ContainerClient", "ContainerCommand", "Executor", "JobHandle", "BatchRunner", "BatchResult", "QueueEvent"]
__version__ = "0.6.1"
