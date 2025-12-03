# src/workers/__init__.py
from .consume_worker import worker_entry as consumer_worker_entry
from .producer_worker import worker_entry as producer_worker_entry

__all__ = ['consumer_worker_entry', 'producer_worker_entry']