"""Discovery-only tool groups from ``docs/tools_group_mvp.txt``.

Group membership is application policy. Definitions come from MCP; returning
them here neither activates tools nor permits executing CST operations.
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from mcp.types import Tool


@dataclass(frozen=True)
class OperationalGroup:
    purpose: str
    members: tuple[str, ...]


GROUP_CATALOGUE = MappingProxyType(
    {
        "session_project": OperationalGroup(
            "Manage an explicitly targeted CST connection and project lifecycle: "
            "connect/disconnect, check connection status, open/create, reported context/tree, "
            "save and close.",
            (
                "cst_connect",
                "cst_disconnect",
                "cst_connection_status",
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


def group_description() -> str:
    """Render the compact model-facing catalogue from the same group policy."""
    return (
        "Search available MCP tool definitions by selecting explicit capability groups. "
        "Pass all groups needed for this lookup in `groups`; [] returns no tools. "
        "Overlapping tools are returned once. Unknown groups or missing members fail "
        "the whole lookup. This only returns definitions: it does not activate or execute "
        "tools, connect to CST, or validate native capabilities.\n"
        + "\n".join(f"- {name}: {group.purpose}" for name, group in GROUP_CATALOGUE.items())
    )


class ToolGroups:
    """Search a detached MCP catalogue using the documented group membership."""

    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError("MCP catalogue contains duplicate tool definitions.")
            self._tools[tool.name] = tool.model_copy(deep=True)
        self.calls: list[dict[str, Any]] = []

    def discover(self, groups: list[str]) -> dict[str, Any]:
        """Return canonical definitions for a whole group union, without dispatch."""
        selected = list(dict.fromkeys(groups))
        unknown = [name for name in selected if name not in GROUP_CATALOGUE]
        names = list(
            dict.fromkeys(
                member
                for name in selected
                if name in GROUP_CATALOGUE
                for member in GROUP_CATALOGUE[name].members
            )
        )
        missing = [name for name in names if name not in self._tools]
        success = not unknown and not missing
        result = {
            "success": success,
            "groups": selected,
            "unknown_groups": unknown,
            "missing_tools": missing,
            "tools": [
                self._tools[name].model_dump(mode="json", by_alias=True, exclude_unset=True)
                for name in names
            ]
            if success
            else [],
        }
        self.calls.append(deepcopy(result))
        return result
