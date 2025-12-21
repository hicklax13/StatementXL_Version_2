"""
Template Knowledge Graph (TKG) builder service.

Builds formula dependency graphs and analyzes template structure.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.services.excel_parser import ExcelParser, ParsedCell, ParsedWorkbook, get_excel_parser

logger = structlog.get_logger(__name__)

# Try to import networkx
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx not installed, graph features limited")


@dataclass
class FormulaNode:
    """Represents a node in the formula dependency graph."""

    address: str  # Full address: Sheet!A1
    sheet: str
    row: int
    column: int
    formula: Optional[str]
    value: Any
    cell_type: str  # input, calculated, label
    references: List[str] = field(default_factory=list)  # Cells this depends on
    referenced_by: List[str] = field(default_factory=list)  # Cells that depend on this


@dataclass
class DependencyGraph:
    """Represents the formula dependency graph for a template."""

    nodes: Dict[str, FormulaNode]
    edges: List[Tuple[str, str]]  # (from, to) - "from" depends on "to"
    input_cells: List[str]
    calculated_cells: List[str]
    label_cells: List[str]
    has_cycles: bool = False
    cycle_nodes: List[str] = field(default_factory=list)


class TKGBuilder:
    """
    Template Knowledge Graph builder.

    Constructs formula dependency graphs and analyzes cell relationships.
    """

    # Regex pattern for cell references
    CELL_REF_PATTERN = re.compile(
        r"(?:\'?([^\'!]+)\'?!)?\$?([A-Za-z]+)\$?(\d+)",
        re.IGNORECASE
    )

    def __init__(self, excel_parser: Optional[ExcelParser] = None):
        """
        Initialize TKG builder.

        Args:
            excel_parser: Excel parser instance.
        """
        self._parser = excel_parser or get_excel_parser()

    def build_graph(self, workbook: ParsedWorkbook) -> DependencyGraph:
        """
        Build dependency graph from parsed workbook.

        Args:
            workbook: Parsed Excel workbook.

        Returns:
            DependencyGraph representing cell dependencies.
        """
        logger.info("Building dependency graph", filename=workbook.filename)

        nodes: Dict[str, FormulaNode] = {}
        edges: List[Tuple[str, str]] = []
        input_cells: List[str] = []
        calculated_cells: List[str] = []
        label_cells: List[str] = []

        # First pass: create all nodes
        for sheet in workbook.sheets:
            for cell in sheet.cells:
                full_address = f"{sheet.name}!{cell.address}"

                # Determine cell type
                if cell.formula:
                    cell_type = "calculated"
                    calculated_cells.append(full_address)
                elif self._is_label(cell):
                    cell_type = "label"
                    label_cells.append(full_address)
                elif cell.value is not None:
                    cell_type = "input"
                    input_cells.append(full_address)
                else:
                    continue  # Skip empty cells

                node = FormulaNode(
                    address=full_address,
                    sheet=sheet.name,
                    row=cell.row,
                    column=cell.column,
                    formula=cell.formula,
                    value=cell.value,
                    cell_type=cell_type,
                )
                nodes[full_address] = node

        # Second pass: build edges from formulas
        for address, node in nodes.items():
            if node.formula:
                refs = self._extract_references(node.formula, node.sheet)
                node.references = refs

                for ref in refs:
                    # Normalize reference
                    norm_ref = self._normalize_reference(ref, node.sheet)

                    if norm_ref in nodes:
                        edges.append((address, norm_ref))
                        nodes[norm_ref].referenced_by.append(address)

        # Check for cycles
        has_cycles = False
        cycle_nodes: List[str] = []

        if NETWORKX_AVAILABLE:
            G = nx.DiGraph()
            G.add_edges_from(edges)

            try:
                cycles = list(nx.simple_cycles(G))
                if cycles:
                    has_cycles = True
                    for cycle in cycles:
                        cycle_nodes.extend(cycle)
                    cycle_nodes = list(set(cycle_nodes))
            except Exception as e:
                logger.warning("Failed to detect cycles", error=str(e))

        result = DependencyGraph(
            nodes=nodes,
            edges=edges,
            input_cells=input_cells,
            calculated_cells=calculated_cells,
            label_cells=label_cells,
            has_cycles=has_cycles,
            cycle_nodes=cycle_nodes,
        )

        logger.info(
            "Dependency graph built",
            nodes=len(nodes),
            edges=len(edges),
            inputs=len(input_cells),
            calculated=len(calculated_cells),
            has_cycles=has_cycles,
        )

        return result

    def _extract_references(self, formula: str, current_sheet: str) -> List[str]:
        """
        Extract cell references from a formula.

        Args:
            formula: Excel formula string.
            current_sheet: Current sheet name for relative references.

        Returns:
            List of full cell addresses (Sheet!Cell).
        """
        if not formula:
            return []

        refs = []
        for match in self.CELL_REF_PATTERN.finditer(formula):
            sheet = match.group(1) or current_sheet
            col = match.group(2).upper()
            row = match.group(3)
            refs.append(f"{sheet}!{col}{row}")

        return refs

    def _normalize_reference(self, ref: str, current_sheet: str) -> str:
        """
        Normalize a cell reference to full format.

        Args:
            ref: Cell reference (may be partial).
            current_sheet: Current sheet for relative refs.

        Returns:
            Full address (Sheet!Cell).
        """
        if "!" not in ref:
            return f"{current_sheet}!{ref}"
        return ref

    def _is_label(self, cell: ParsedCell) -> bool:
        """Check if a cell is likely a label."""
        if cell.formula:
            return False
        if cell.value is None:
            return False
        if isinstance(cell.value, str):
            # Labels are typically non-numeric strings
            try:
                float(cell.value.replace(",", "").replace("$", ""))
                return False
            except (ValueError, AttributeError):
                return True
        return False

    def to_graphviz(self, graph: DependencyGraph) -> str:
        """
        Export graph to Graphviz DOT format.

        Args:
            graph: Dependency graph.

        Returns:
            DOT format string.
        """
        lines = ["digraph TemplateGraph {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        lines.append("")

        # Color nodes by type
        for address, node in graph.nodes.items():
            color = {
                "input": "lightgreen",
                "calculated": "lightblue",
                "label": "lightyellow",
            }.get(node.cell_type, "white")

            label = address.replace("!", "\\n")
            lines.append(f'  "{address}" [label="{label}", fillcolor={color}, style=filled];')

        lines.append("")

        # Add edges
        for from_addr, to_addr in graph.edges:
            lines.append(f'  "{from_addr}" -> "{to_addr}";')

        lines.append("}")
        return "\n".join(lines)

    def to_json(self, graph: DependencyGraph) -> Dict[str, Any]:
        """
        Export graph to JSON-serializable format.

        Args:
            graph: Dependency graph.

        Returns:
            JSON-serializable dictionary.
        """
        return {
            "nodes": {
                addr: {
                    "address": node.address,
                    "sheet": node.sheet,
                    "row": node.row,
                    "column": node.column,
                    "cell_type": node.cell_type,
                    "formula": node.formula,
                    "references": node.references,
                    "referenced_by": node.referenced_by,
                }
                for addr, node in graph.nodes.items()
            },
            "edges": graph.edges,
            "input_cells": graph.input_cells,
            "calculated_cells": graph.calculated_cells,
            "label_cells": graph.label_cells,
            "has_cycles": graph.has_cycles,
            "cycle_nodes": graph.cycle_nodes,
        }


# Singleton instance
_builder_instance: Optional[TKGBuilder] = None


def get_tkg_builder() -> TKGBuilder:
    """Get singleton TKGBuilder instance."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = TKGBuilder()
    return _builder_instance
