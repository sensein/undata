from typing import Protocol, runtime_checkable

from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload


@runtime_checkable
class SchemaAdapter(Protocol):
    source_name: str
    source_format: str

    def load(self, path_or_url: str) -> None:
        """Deprecated shim — delegates to load_file(path_or_url).

        Kept for backward compatibility with existing call sites.
        """
        ...

    def load_code(self) -> None:
        """Load schema via Python library introspection.

        Post-condition: adapter ready to call extract_elements("code").
        Raises ImportError if the required library is not installed;
        message MUST name the missing package.
        """
        ...

    def load_file(self, path_or_url: str) -> None:
        """Load schema from a local path/directory or remote URL.

        Post-condition: adapter ready to call extract_elements("file").
        Raises ValueError if path_or_url is empty and adapter has no default.
        """
        ...

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        """Return normalized data elements from the loaded schema.

        mode='code'  — uses data from load_code()
        mode='file'  — uses data from load_file()
        mode='both'  — merges both paths; deduplicates by source_local_id
        """
        ...

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        """Return class/category groupings from the loaded schema.

        Same mode semantics as extract_elements().
        """
        ...

    def get_version_info(self) -> dict:
        """Return version_tag and content_hash for SchemaSource registration."""
        ...
