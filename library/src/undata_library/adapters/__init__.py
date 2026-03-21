"""Adapter framework for schema ingestion."""

from .base import BaseAdapter, ClassifiedEntity
from .classifier import classify_entity

__all__ = ["BaseAdapter", "ClassifiedEntity", "classify_entity"]
