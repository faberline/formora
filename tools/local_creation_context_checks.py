#!/usr/bin/env python3
"""Keep the complete prior gates and exact test counts for issue #44."""
from local_selection_checks import main


if __name__=='__main__':
    main(expected_rust_tests=116,expected_python_tests=49,
         extra_examples=('remaining_primitive_bench','creation_context_bench'),
         extra_source_directories=('docs/evidence/creation-contexts/source',))
