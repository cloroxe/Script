"""Planificateur de bâtiment modulaire (maths pures, coordonnées éditeur UEFN en cm).

Convention : X avant, Y droite, Z haut. Les modules de mur ont leur longueur sur
l'axe X local, pivot centré. Yaw en degrés.
"""
from __future__ import annotations

import math
from typing import Any

from .errors import VibeError

MAX_PLACEMENTS = 2000


def _rotate(x: float, y: float, yaw_deg: float) -> tuple[float, float]:
    rad = math.radians(yaw_deg)
    return x * math.cos(rad) - y * math.sin(rad), x * math.sin(rad) + y * math.cos(rad)


def plan_building(
    *,
    width_cm: float,
    depth_cm: float,
    floors: int = 1,
    module_cm: float = 400.0,
    floor_height_cm: float = 300.0,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    yaw_deg: float = 0.0,
    floor_slab: bool = True,
    roof: bool = True,
    door: bool = True,
) -> list[dict[str, Any]]:
    if min(width_cm, depth_cm, module_cm, floor_height_cm) <= 0 or floors < 1:
        raise VibeError("width_cm, depth_cm, module_cm, floor_height_cm > 0 et floors >= 1 requis.")
    nx = max(1, round(width_cm / module_cm))
    ny = max(1, round(depth_cm / module_cm))
    total_w, total_d = nx * module_cm, ny * module_cm
    estimated = floors * (2 * nx + 2 * ny) + (floors + (1 if roof else 0)) * nx * ny
    if estimated > MAX_PLACEMENTS:
        raise VibeError(
            f"Plan trop gros ({estimated} pièces > {MAX_PLACEMENTS}). Réduis les dimensions ou augmente module_cm."
        )

    placements: list[dict[str, Any]] = []

    def add(role: str, lx: float, ly: float, z: float, local_yaw: float) -> None:
        rx, ry = _rotate(lx, ly, yaw_deg)
        placements.append(
            {
                "role": role,
                "location": [round(origin[0] + rx, 2), round(origin[1] + ry, 2), round(origin[2] + z, 2)],
                "rotation": [0.0, round((local_yaw + yaw_deg) % 360, 2), 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
        )

    for floor in range(floors):
        z = floor * floor_height_cm
        if floor_slab:
            for ix in range(nx):
                for iy in range(ny):
                    add("floor", -total_w / 2 + (ix + 0.5) * module_cm, -total_d / 2 + (iy + 0.5) * module_cm, z, 0.0)
        door_ix = nx // 2
        for ix in range(nx):  # murs avant (y négatif) et arrière
            lx = -total_w / 2 + (ix + 0.5) * module_cm
            is_door = door and floor == 0 and ix == door_ix
            add("doorway" if is_door else "wall", lx, -total_d / 2, z, 0.0)
            add("wall", lx, total_d / 2, z, 0.0)
        for iy in range(ny):  # murs gauche et droit
            ly = -total_d / 2 + (iy + 0.5) * module_cm
            add("wall", -total_w / 2, ly, z, 90.0)
            add("wall", total_w / 2, ly, z, 90.0)

    if roof:
        z = floors * floor_height_cm
        for ix in range(nx):
            for iy in range(ny):
                add("roof", -total_w / 2 + (ix + 0.5) * module_cm, -total_d / 2 + (iy + 0.5) * module_cm, z, 0.0)
    return placements


def summarize(placements: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in placements:
        counts[item["role"]] = counts.get(item["role"], 0) + 1
    return counts
