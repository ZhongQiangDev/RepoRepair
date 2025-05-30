from tree_sitter import Language
import warnings

warnings.simplefilter('ignore', FutureWarning)

Language.build_library(
    # Store the library in the `build` directory
    'build/my-languages.so',

    # Include one or more languages
    [
        'vendor/tree-sitter-javascript',
        'vendor/tree-sitter-typescript/typescript'
    ]
)
