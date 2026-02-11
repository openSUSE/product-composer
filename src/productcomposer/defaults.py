"""
Product composer executes programs that have their own defaults.
These defaults rarely change, but if they do, they'll impact product composes.

To avoid such unexpected changes, we define our defaults here
and explicitly pass them to the programs.
"""


CREATEREPO_CHECKSUM_TYPE: str = "sha512"
CREATEREPO_GENERAL_COMPRESS_TYPE: str = "zstd"
ISO_CHECKSUM_TYPE: str = "sha512"
