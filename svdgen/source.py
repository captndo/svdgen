"""Source metadata and traceability for SVD elements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree


@dataclass(frozen=True)
class SourceInfo:
    """Source location of a single SVD element."""

    file_path: Path
    line: int | None = None
    element_tag: str | None = None


class SourceMap:
    """Maps dot-separated SVD element paths to source locations.

    Built by walking the raw lxml tree and recording ``element.sourceline``
    for each named element.  Paths use dot notation matching the flattened
    model produced by cmsis-svd::

        "GPIOA"              -> peripheral element
        "GPIOA.MODER"        -> register element
        "GPIOA.MODER.MODE0"  -> field element
        "GPIOA.GPIOA_IRQ"    -> interrupt element
    """

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._entries: dict[str, SourceInfo] = {}

    # -- public interface -----------------------------------------------------

    def lookup(self, path: str) -> SourceInfo | None:
        return self._entries.get(path)

    @property
    def paths(self) -> list[str]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, path: str) -> bool:
        return path in self._entries

    # -- construction ---------------------------------------------------------

    @classmethod
    def from_svd(cls, file_path: Path) -> SourceMap:
        smap = cls(file_path)
        tree = etree.parse(str(file_path))
        smap._build(tree.getroot())
        return smap

    def _build(self, root: etree._Element) -> None:
        device_name = root.findtext("name")
        if device_name:
            self._record(device_name, root, "device")

        for periph_node in root.findall(".//peripheral"):
            self._walk_peripheral(periph_node)

    def _walk_peripheral(self, node: etree._Element) -> None:
        name = node.findtext("name")
        if not name:
            return
        self._record(name, node, "peripheral")

        registers_node = node.find("registers")
        if registers_node is not None:
            self._walk_register_container(name, registers_node, prefix="")

        for irq_node in node.findall("interrupt"):
            irq_name = irq_node.findtext("name")
            if irq_name:
                self._record(f"{name}.{irq_name}", irq_node, "interrupt")

    def _walk_register_container(
        self, periph_path: str, container: etree._Element, *, prefix: str
    ) -> None:
        for reg_node in container.findall("register"):
            reg_name = reg_node.findtext("name")
            if not reg_name:
                continue
            full_name = f"{prefix}{reg_name}" if prefix else reg_name
            reg_path = f"{periph_path}.{full_name}"
            self._record(reg_path, reg_node, "register")

            for field_node in reg_node.findall(".//field"):
                field_name = field_node.findtext("name")
                if field_name:
                    self._record(f"{reg_path}.{field_name}", field_node, "field")

        for cluster_node in container.findall("cluster"):
            cluster_name = cluster_node.findtext("name")
            if not cluster_name:
                continue
            self._walk_register_container(
                periph_path, cluster_node, prefix=f"{prefix}{cluster_name}_"
            )

    def _record(self, path: str, node: etree._Element, tag: str) -> None:
        self._entries[path] = SourceInfo(
            file_path=self._file_path,
            line=node.sourceline,
            element_tag=tag,
        )
