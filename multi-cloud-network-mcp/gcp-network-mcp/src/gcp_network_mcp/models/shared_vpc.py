"""Normalized models for Shared VPC host/service-project relationships."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SharedVpcHostStatus(BaseModel):
    """Whether a project is a Shared VPC host, from
    ``ProjectsClient.get`` (``Project.xpn_project_status``)."""

    project_id: str
    xpn_project_status: str


class SharedVpcServiceProject(BaseModel):
    """One service project attached to a Shared VPC host, from
    ``ProjectsClient.get_xpn_resources``."""

    resource_id: str
    resource_type: str


class SharedVpcHostRelationship(BaseModel):
    """The full Shared VPC picture for one host project: its status plus
    every attached service project, from ``get_xpn_host``/
    ``get_xpn_resources``."""

    host_project_id: str
    service_projects: list[SharedVpcServiceProject] = Field(default_factory=list)


__all__ = ["SharedVpcHostRelationship", "SharedVpcHostStatus", "SharedVpcServiceProject"]
