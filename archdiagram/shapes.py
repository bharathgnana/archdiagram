"""Shared geometry and palette for explicit workflow shapes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShapeStyle:
    width: int
    height: int
    fill: str
    stroke: str
    drawio: str
    pptx: str


SHAPES: dict[str, ShapeStyle] = {
    "start": ShapeStyle(130, 50, "#D5E8D4", "#82B366", "rounded=1;arcSize=50;", "roundRect"),
    "end": ShapeStyle(130, 50, "#F8CECC", "#B85450", "rounded=1;arcSize=50;", "roundRect"),
    "process": ShapeStyle(160, 60, "#DAE8FC", "#6C8EBF", "rounded=1;arcSize=8;", "roundRect"),
    "decision": ShapeStyle(140, 80, "#FFE6CC", "#D79B00", "rhombus;", "diamond"),
    "io": ShapeStyle(160, 60, "#FFF2CC", "#D6B656", "shape=parallelogram;", "parallelogram"),
    "document": ShapeStyle(160, 70, "#E1D5E7", "#9673A6", "shape=document;", "flowChartDocument"),
    "data_store": ShapeStyle(140, 70, "#E8F4F9", "#2EA6B0", "shape=mxgraph.flowchart.database;", "can"),
}
