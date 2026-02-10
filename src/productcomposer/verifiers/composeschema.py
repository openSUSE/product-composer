"""Schema definition for productcompose files"""

from pydantic import BaseModel, Field

from typing import Literal
from typing import Optional


class compose_schema_iso(BaseModel):
    publisher: Optional[str] = None
    volume_id: Optional[str] = None
    tree: Optional[str] = None
    base: Optional[str] = None
    joliet: Optional[bool] = True
    checksums: Optional[list[str]] = None


_compose_schema_supportstatus = Literal[
    'l3', 'l2', 'acc', 'unsupported', '=l3', '=l2', '=acc', '=unsupported'
]


class compose_schema_packageset(BaseModel):
    name: Optional[str] = "main"
    supportstatus: Optional[str] = None
    flavors: Optional[list[str]] = None
    architectures: Optional[list[str]] = None
    add: Optional[list[str]] = None
    sub: Optional[list[str]] = None
    intersect: Optional[list[str]] = None
    packages: Optional[list[str]] = None


class compose_schema_scc_cpe(BaseModel):
    cpe: str
    online: Optional[bool] = None


class compose_schema_scc(BaseModel):
    description: Optional[str] = None
    family: Optional[str] = None
    product_class: Optional[str] = Field(default=None, alias='product-class')
    free: Optional[bool] = False
    predecessors: Optional[list[compose_schema_scc_cpe]] = None
    product_name_prefix: Optional[str] = Field(default=None, alias='product-name-prefix')  # default is SLE-Product- in scc converter
    shortname: Optional[str] = None
    base_products: Optional[list[compose_schema_scc_cpe]] = None
    root_products: Optional[list[compose_schema_scc_cpe]] = None
    recommended_for: Optional[list[compose_schema_scc_cpe]] = None
    migration_extra_for: Optional[list[compose_schema_scc_cpe]] = None


compose_schema_build_option = Literal[
    'abort_on_empty_updateinfo',
    'add_slsa_provenance',
    'base_skip_packages',
    'block_updates_under_embargo',
    'hide_flavor_in_product_directory_name',
    'ignore_missing_packages',
    'no_product_provides',
    'skip_updateinfos',
    'take_all_available_versions',
    'updateinfo_packages_only',
    'OBS_unordered_product_repos',
]

compose_schema_source_and_debug = Literal['drop', 'include', 'split']
compose_schema_repodata = Literal['all', 'split']

class compose_schema(BaseModel):
    architectures: Optional[list[str]] = []
    name: Optional[str] = None
    version: Optional[str] = None
    version_from_package: Optional[str] = None
    edition: Optional[str] = None
    update: Optional[str] = None
    product_type: Optional[str] = Field(default=None, alias='product-type')
    product_directory_name: Optional[str] = None
    content: Optional[list[str]] = ['main']
    unpack: Optional[list[str]] = []
    repodata: Optional[compose_schema_repodata] = None
    summary: Optional[str] = None
    debug: Optional[compose_schema_source_and_debug] = None
    source: Optional[compose_schema_source_and_debug] = None
    build_options: Optional[list[compose_schema_build_option]] = []
    scc: Optional[compose_schema_scc] = None
    iso: Optional[compose_schema_iso] = None
    installcheck: Optional[list[Literal['ignore_errors']]] | None = None

    set_updateinfo_from: Optional[str] = None
    set_updateinfo_id_prefix: Optional[str] = ""
    block_updates_under_embargo: Optional[str] = None

class ComposeSchema(compose_schema, BaseModel):
    product_compose_schema: Literal['0.1', '0.2']
    vendor: str
    bcntsynctag: Optional[str] = None
    milestone: Optional[str] = None

    flavors: Optional[dict[str, compose_schema]] = {}
    packagesets: Optional[list[compose_schema_packageset]] = None
