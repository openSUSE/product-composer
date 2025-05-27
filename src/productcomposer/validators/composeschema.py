
from schema import Schema, And, Or, Optional, SchemaError

compose_schema_iso = Schema({
    Optional('publisher'): str,
    Optional('volume_id'): str,
    Optional('tree'): str,
    Optional('base'): str,
})
compose_schema_packageset = Schema({
    Optional('name'): str,
    Optional('supportstatus'): str,
    Optional('override_supportstatus'): bool,
    Optional('flavors'): [str],
    Optional('architectures'): [str],
    Optional('add'): [str],
    Optional('sub'): [str],
    Optional('intersect'): [str],
    Optional('packages'): Or(None, [str]),
})
compose_schema_scc_cpe = Schema({
    'cpe': str,
    Optional('online'): bool,
})
compose_schema_scc = Schema({
    Optional('description'): str,
    Optional('family'): str,
    Optional('product-class'): str,
    Optional('free'): bool,
    Optional('predecessors'): [compose_schema_scc_cpe],
    Optional('shortname'): str,
    Optional('base-products'): [compose_schema_scc_cpe],
    Optional('root-products'): [compose_schema_scc_cpe],
    Optional('recommended-for'): [compose_schema_scc_cpe],
    Optional('migration-extra-for'): [compose_schema_scc_cpe],
})
compose_schema_build_option = Schema(
    Or(
        'add_slsa_provenance',
        'base_skip_packages',
        'block_updates_under_embargo',
        'hide_flavor_in_product_directory_name',
        'ignore_missing_packages',
        'skip_updateinfos',
        'take_all_available_versions',
        'updateinfo_packages_only',
    )
)
compose_schema_source_and_debug = Schema(
    Or(
        'drop',
        'include',
        'split',
    )
)
compose_schema_repodata = Schema(
    Or(
        'all',
        'split',
    )
)
compose_schema_flavor = Schema({
    Optional('architectures'): [str],
    Optional('name'): str,
    Optional('version'): str,
    Optional('update'): str,
    Optional('edition'): str,
    Optional('product-type'): str,
    Optional('product_directory_name'): str,
    Optional('repodata'): compose_schema_repodata,
    Optional('summary'): str,
    Optional('debug'): compose_schema_source_and_debug,
    Optional('source'): compose_schema_source_and_debug,
    Optional('build_options'): Or(None, [compose_schema_build_option]),
    Optional('scc'): compose_schema_scc,
    Optional('iso'): compose_schema_iso,
})

compose_schema = Schema({
    'product_compose_schema': str,
    'vendor': str,
    'name': str,
    'version': str,
    Optional('update'): str,
    'product-type': str,
    'summary': str,
    Optional('bcntsynctag'): str,
    Optional('milestone'): str,
    Optional('scc'): compose_schema_scc,
    Optional('iso'): compose_schema_iso,
    Optional('installcheck'): Or(None, ['ignore_errors']),
    Optional('build_options'): Or(None, [compose_schema_build_option]),
    Optional('architectures'): [str],

    Optional('product_directory_name'): str,
    Optional('set_updateinfo_from'): str,
    Optional('set_updateinfo_id_prefix'): str,
    Optional('block_updates_under_embargo'): str,
    Optional('debug'): compose_schema_source_and_debug,
    Optional('source'): compose_schema_source_and_debug,
    Optional('repodata'): compose_schema_repodata,

    Optional('flavors'): {str: compose_schema_flavor},
    Optional('packagesets'): [compose_schema_packageset],
    Optional('unpack'): [str],
})
