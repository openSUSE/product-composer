"""Schema definition for productcompose files"""

from pydantic import BaseModel

from typing import Literal
from typing import Optional


class compose_schema_iso(BaseModel):
    publisher: Optional[str]
    volume_id: Optional[str]
    tree: Optional[str]
    base: Optional[str]


class compose_schema_packageset(BaseModel):
    name: Optional[str]
    supportstatus: Optional[str]
    flavors: Optional[list[str]]
    architectures: Optional[list[str]]
    add: Optional[list[str]]
    sub: Optional[list[str]]
    intersect: Optional[list[str]]
    supportstatus: Optional[str]
    override_supportstatus: Optional[bool]
    packages: Optional[list[str]]


class compose_schema_scc_cpe(BaseModel):
    cpe: str
    online: Optional[bool]


class compose_schema_scc(BaseModel):
    description: Optional[str]
    family: Optional[str]
    product_class: Optional[str]
    free: Optional[bool]
    predecessors: Optional[compose_schema_scc_cpe]
    shortname: Optional[str]
    base_products: Optional[list[compose_schema_scc_cpe]]
    root_products: Optional[list[compose_schema_scc_cpe]]
    recommended_for: Optional[list[compose_schema_scc_cpe]]
    migration_extra_for: Optional[list[compose_schema_scc_cpe]]


compose_schema_build_option = Literal[
    'add_slsa_provenance',
    'base_skip_packages',
    'block_updates_under_embargo',
    'hide_flavor_in_product_directory_name',
    'ignore_missing_packages',
    'skip_updateinfos',
    'take_all_available_versions',
    'updateinfo_packages_only',
]

compose_schema_source_and_debug = Literal['drop', 'include', 'split']
compose_schema_repodata = Literal['all', 'split']


class compose_schema_flavor(BaseModel):
    architectures: Optional[list[str]]
    name: Optional[str]
    version: Optional[str]
    update: Optional[str]
    edition: Optional[str]
    product_type: Optional[str]
    product_directory_name: Optional[str]
    packageset: Optional[str]
    repodata: Optional[compose_schema_repodata]
    summary: Optional[str]
    debug: Optional[compose_schema_source_and_debug]
    source: Optional[compose_schema_source_and_debug]
    build_options: Optional[list[compose_schema_build_option]]
    scc: Optional[compose_schema_scc]
    iso: Optional[compose_schema_iso]


class ComposeSchema(BaseModel):
    product_compose_schema: str
    vendor: str
    name: str
    version: str
    update: Optional[str]
    product_type: Optional[str]
    summary: str
    bcntsynctag: Optional[str]
    milestone: Optional[str]
    scc: compose_schema_scc
    iso: compose_schema_iso
    installcheck: Optional[list[Literal['ignore_errors']]] | None
    build_options: Optional[list[compose_schema_build_option]]
    architectures: Optional[list[str]]

    product_directory_name: Optional[str]
    set_updateinfo_from: Optional[str]
    set_updateinfo_id_prefix: Optional[str]
    block_updates_under_embargo: Optional[str]

    debug: Optional[compose_schema_source_and_debug]
    source: Optional[compose_schema_source_and_debug]
    repodata: Optional[compose_schema_repodata]

    flavors: Optional[compose_schema_flavor]
    packagesets: Optional[list[compose_schema_packageset]]
    unpack: Optional[list[str]]
