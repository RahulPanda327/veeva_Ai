"""Shared schema for the manager → employee → territory filter tree.

Returned inside the summary responses of both MyInsights (Territory
Prioritization) and Action Center so the UI can render cascading
manager / employee / territory dropdowns. Selecting a territory and
passing its id back as ?territory_id= re-scopes the module data.

Shape (matches the field-force org hierarchy verbatim):

    { "manager_id": [ { manager_id, manager_name,
                        employee_id: [ { employee_id, employee_name,
                                         territory_id: [ { territory_id, territory_name } ] } ] } ] }
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class TerritoryFilterItem(BaseModel):
    territory_id: str = Field(description="Territory_Durable_Id, e.g. A0E000000013031")
    territory_name: Optional[str] = Field(default=None, description="Territory owner name, e.g. Natalie Birkin")


class EmployeeFilterItem(BaseModel):
    employee_id: str = Field(description="Employee_Durable_Id, e.g. A09000000000149")
    employee_name: Optional[str] = None
    territory_id: List[TerritoryFilterItem] = Field(default_factory=list, description="Territories owned by this employee")


class ManagerFilterItem(BaseModel):
    manager_id: str = Field(description="Manager_Employee_Durable_Id, e.g. A09000000049003")
    manager_name: Optional[str] = None
    employee_id: List[EmployeeFilterItem] = Field(default_factory=list, description="Employees reporting to this manager")


class OrgFilters(BaseModel):
    manager_id: List[ManagerFilterItem] = Field(default_factory=list)
