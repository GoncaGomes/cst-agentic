"""Approved #9 catalogue and task-local whole-set schema selection.

Availability is neither native capability evidence nor execution permission.
The server supplies canonical schemas, never this application's inventory policy.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from mcp.types import Tool

from .canonical_schema import canonical_validator


@dataclass(frozen=True)
class OperationalGroup:
    purpose: str
    members: tuple[str, ...]


# #9's final resolution, amended by the reviewed #20 deletion-tool request.
GROUP_CATALOGUE = MappingProxyType(
    {
        "session_project": OperationalGroup(
            "Manage an explicitly targeted CST connection and project lifecycle: "
            "connect/disconnect, open/create, reported context/tree, save and close.",
            (
                "cst_connect",
                "cst_disconnect",
                "cst_open_project",
                "cst_create_project",
                "cst_save_project",
                "cst_close_project",
                "cst_project_info",
                "cst_project_tree",
            ),
        ),
        "project_context": OperationalGroup(
            "Read reported project context/tree, save and export structure views while working "
            "in another capability. View export is not visual verification.",
            (
                "cst_project_info",
                "cst_project_tree",
                "cst_save_project",
                "cst_export_structure_views",
            ),
        ),
        "parameters": OperationalGroup(
            "Create/change or explicitly delete design parameters and inspect names/evaluated "
            "values. Existing get/list tools do not establish stored expressions.",
            (
                "cst_set_parameter",
                "cst_get_parameter",
                "cst_list_parameters",
                "cst_delete_parameter",
            ),
        ),
        "materials_basic": OperationalGroup(
            "Inspect bundled material entries, load exact library entries first where suitable, "
            "or explicitly define/assign/delete ordinary project materials. Bundled queries do "
            "not verify project material properties.",
            (
                "cst_create_material",
                "cst_create_lossy_metal",
                "cst_load_material",
                "cst_list_materials",
                "cst_get_material_info",
                "cst_assign_material",
                "cst_delete_material",
            ),
        ),
        "geometry_basic": OperationalGroup(
            "Create common solid primitives and the supported wire/bondwire geometry.",
            (
                "cst_create_brick",
                "cst_create_cylinder",
                "cst_create_cone",
                "cst_create_sphere",
                "cst_create_wire",
            ),
        ),
        "geometry_profiles": OperationalGroup(
            "Create explicit profile-based curves/solids and less frequent shapes without "
            "loading their schemas for ordinary primitive work.",
            (
                "cst_create_extrude",
                "cst_create_polygon_extrude",
                "cst_create_polygon3d",
                "cst_create_analytical_curve",
                "cst_create_face_from_curves",
                "cst_create_loft",
                "cst_create_ecylinder",
                "cst_create_torus",
            ),
        ),
        "solid_operations": OperationalGroup(
            "Apply native boolean operations and supported translations, rotations, mirrors, "
            "scales and copies to identified geometry.",
            (
                "cst_boolean_add",
                "cst_boolean_subtract",
                "cst_boolean_intersect",
                "cst_boolean_insert",
                "cst_transform_translate",
                "cst_transform_rotate",
                "cst_transform_mirror",
                "cst_transform_scale",
            ),
        ),
        "simulation_domain": OperationalGroup(
            "Set the frequency band, boundary faces, background and justified symmetry using "
            "each tool's actual units/argument contract.",
            (
                "cst_set_frequency_range",
                "cst_set_boundary",
                "cst_set_background",
                "cst_set_symmetry",
            ),
        ),
        "ports_basic": OperationalGroup(
            "Create ordinary waveguide/discrete ports and supported lumped elements, list ports "
            "or delete an explicitly identified port. Numeric coordinate fields do not preserve "
            "parameter-expression dependencies.",
            (
                "cst_add_waveguide_port",
                "cst_add_discrete_port",
                "cst_add_lumped_element",
                "cst_list_ports",
                "cst_delete_port",
            ),
        ),
        "solver_time_domain": OperationalGroup(
            "Configure the ordinary time-domain solver and read available solver information.",
            ("cst_configure_time_domain_solver", "cst_get_solver_info"),
        ),
        "solver_frequency_domain": OperationalGroup(
            "Configure the ordinary frequency-domain solver and read available solver information.",
            ("cst_configure_frequency_domain_solver", "cst_get_solver_info"),
        ),
        "mesh_basic": OperationalGroup(
            "Configure compatible mesh settings, density, refinement/adaptation and read "
            "available mesh information.",
            (
                "cst_set_mesh_type",
                "cst_set_mesh_density",
                "cst_add_mesh_refinement",
                "cst_set_adaptive_mesh",
                "cst_get_mesh_info",
            ),
        ),
        "field_monitors": OperationalGroup(
            "Define supported field monitors before a solve.",
            ("cst_add_field_monitor",),
        ),
        "simulation_run": OperationalGroup(
            "Launch asynchronously, inspect progress, perform bounded waits or request stop. "
            "Report observed state without equating solver idleness with numerical success.",
            (
                "cst_run_simulation_async",
                "cst_get_simulation_status",
                "cst_wait_for_simulation",
                "cst_stop_simulation",
            ),
        ),
        "diagnostics": OperationalGroup(
            "Read logs, check a supplied setup description or explicitly invalidate results when "
            "authorized. Setup-description checking is not live project validation.",
            ("cst_read_project_log", "cst_delete_results", "cst_check_model_setup"),
        ),
        "reference": OperationalGroup(
            "Search and read installed official CST help; documentation access does not "
            "authorize arbitrary code execution.",
            ("cst_search_help", "cst_read_help"),
        ),
        "cad_io": OperationalGroup(
            "Import/export supported CAD using explicitly scoped paths and targets.",
            ("cst_import_cad", "cst_export_cad"),
        ),
        "connectors": OperationalGroup(
            "Create the specifically supported parametric edge-launch SMA connector when its "
            "assumptions match the requested model.",
            ("cst_add_sma_edge_connector",),
        ),
    }
)
GROUPS = MappingProxyType({name: group.members for name, group in GROUP_CATALOGUE.items()})

STARTUP_MCP = ("cst_connection_status", "cst_project_info")
APPROVED_MCP_TOOLS = frozenset(STARTUP_MCP).union(*GROUPS.values())
ACTIVE_LIMIT = 16

GROUP_GUIDANCE = (
    "Select the smallest suitable named group set with discover_tools. Selection replaces the "
    "whole set; [] returns to startup. At most 16 total unique functions are active, including "
    "connection status, reported project info and discovery; overlaps count once. "
    "Discovery must be the only call in its batch. It activates canonical definitions on the "
    "next internal request, without granting execution permission. "
    "Clarifications and intermediate stages preserve selection; established separate "
    "objectives reset to startup. Ask if the task boundary is unclear. Project info is reported "
    "context, not independent target identity. Unexpected native dialogs require human "
    "intervention. Approved groups:\n"
    + "\n".join(
        f"{name} ({len(group.members)}): {group.purpose}" for name, group in GROUP_CATALOGUE.items()
    )
)


def discovery_definition() -> Tool:
    return Tool(
        name="discover_tools",
        description="Replace selected groups; schemas activate on the next internal request.",
        input_schema={
            "type": "object",
            "properties": {
                "groups": {"type": "array", "items": {"type": "string", "enum": list(GROUPS)}}
            },
            "required": ["groups"],
            "additionalProperties": False,
        },
    )


class ToolDiscovery:
    """Detached accepted catalogue and selection; never dispatches an MCP tool."""

    def __init__(self, catalogue: Sequence[Tool]) -> None:
        self._catalogue: dict[str, Tool] = {}
        self._reviewed_schemas: dict[str, str] = {}
        self._unavailable: dict[str, str] = {}
        self.blocker: str | None = None
        self._groups: tuple[str, ...] = ()
        self._rejections = 0
        self._seen: set[tuple[str, ...]] = {()}
        self.pause_reason: str | None = None
        self.refresh(catalogue)

    def refresh(self, catalogue: Sequence[Tool]) -> str:
        """Called by the coordinator only at an admitted settled boundary.

        Keep the original accepted same-name schemas even through disappearance,
        so removal/reintroduction cannot evade the review requirement. Explicit
        refresh does not reset task-local loop tracking or any execution state.
        """
        counts = Counter(tool.name for tool in catalogue)
        accepted: dict[str, Tool] = {}
        unavailable: dict[str, str] = {}
        for tool in deepcopy(catalogue):
            name = tool.name
            if name not in APPROVED_MCP_TOOLS:
                continue
            if counts[name] != 1:
                unavailable[name] = "duplicate canonical name"
                continue
            try:
                canonical_validator(tool.input_schema)
                key = json.dumps(tool.input_schema, sort_keys=True, allow_nan=False)
            except Exception:
                unavailable[name] = "unfaithful or unsupported canonical schema"
                continue
            if name in self._reviewed_schemas and key != self._reviewed_schemas[name]:
                unavailable[name] = "same-name schema drift requires review"
                continue
            self._reviewed_schemas[name] = key
            accepted[name] = tool
        for name in APPROVED_MCP_TOOLS - accepted.keys() - unavailable.keys():
            unavailable[name] = "missing canonical tool"
        self._catalogue, self._unavailable = accepted, unavailable
        self._groups = ()
        missing_startup = [name for name in STARTUP_MCP if name not in accepted]
        self.blocker = (
            "Required startup tools unavailable: "
            + "; ".join(f"{name}: {unavailable[name]}" for name in missing_startup)
            if missing_startup
            else None
        )
        disabled = [
            f"{group} ({'; '.join(f'{n}: {unavailable[n]}' for n in names if n in unavailable)})"
            for group, names in GROUPS.items()
            if any(n in unavailable for n in names)
        ]
        return self.blocker or (
            "Catalogue refreshed; selection reset to startup. "
            + (
                "Unavailable groups: " + ", ".join(disabled)
                if disabled
                else "All approved groups available."
            )
        )

    @property
    def tools(self) -> tuple[Tool, ...]:
        if self.blocker is not None:
            return ()  # Coordinator refuses a request, never transmits a smaller startup.
        names = dict.fromkeys((*STARTUP_MCP, *(n for g in self._groups for n in GROUPS[g])))
        return (*deepcopy(tuple(self._catalogue[name] for name in names)), discovery_definition())

    def _result(self, accepted: bool, requested: Any, reason: str) -> dict[str, Any]:
        return {
            "accepted": accepted,
            "reason": reason,
            "requested_groups": deepcopy(requested),
            "current_groups": list(self._groups),
            "active_tools": [tool.name for tool in self.tools],
            "visible_count": len(self.tools),
            "limit": ACTIVE_LIMIT,
            "activation": "next internal request" if accepted else "unchanged",
        }

    def reject(self, reason: str, requested: Any = None) -> dict[str, Any]:
        self._rejections += 1
        if self._rejections >= 3:
            self.pause_reason = (
                "Discovery paused after three consecutive rejected selections. " + reason
            )
        return self._result(False, requested, reason)

    def successful_work(self) -> None:
        self._seen.clear()

    def block_refresh(self) -> str:
        self._groups = ()
        self.blocker = "Catalogue refresh failed; current availability unverified."
        return self.blocker

    def accepts_definition(self, tool: Tool) -> bool:
        canonical = self._catalogue.get(tool.name)
        return (
            self.blocker is None
            and canonical is not None
            and canonical.input_schema == tool.input_schema
        )

    def reset_task(self) -> None:
        self._groups = ()
        self._seen = {()}
        self._rejections = 0
        self.pause_reason = None

    def resume_with_guidance(self) -> None:
        self._seen.clear()
        self._rejections = 0
        self.pause_reason = None

    def select(self, arguments: dict[str, Any]) -> dict[str, Any]:
        groups = arguments.get("groups")
        if set(arguments) != {"groups"}:
            return self.reject(
                "Expected only required groups argument; missing groups or extra keys: "
                + ", ".join(sorted(set(arguments) - {"groups"})),
                groups,
            )
        if not isinstance(groups, list) or any(not isinstance(g, str) for g in groups):
            return self.reject("groups must be an array of group identifier strings.", groups)
        unknown = sorted(set(groups) - GROUPS.keys())
        if unknown:
            return self.reject("Unknown groups: " + ", ".join(unknown), groups)
        proposed = tuple(sorted(set(groups)))
        names = set(STARTUP_MCP).union(*(GROUPS[g] for g in proposed))
        count = len(names) + 1
        unavailable = sorted(names - self._catalogue.keys())
        if unavailable:
            return self.reject(
                "Unavailable canonical tools: "
                + "; ".join(f"{name}: {self._unavailable[name]}" for name in unavailable),
                groups,
            )
        if count > ACTIVE_LIMIT:
            return self.reject(
                f"Proposed visible count {count} exceeds limit {ACTIVE_LIMIT}.", groups
            )
        if proposed in self._seen:
            reason = (
                "Repeated normalized effective group set without successful non-discovery work."
            )
            result = self.reject(reason, groups)
            self.pause_reason = reason
            return result
        self._groups = proposed
        self._seen.add(proposed)
        self._rejections = 0
        return self._result(True, groups, "Selection accepted.")
