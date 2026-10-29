#!/usr/bin/env python3
"""Keep every prior gate and pin the complete expected test counts for issue #42."""
from local_selection_checks import main


if __name__=='__main__':
    main(expected_rust_tests=107,expected_python_tests=49,extra_examples=('remaining_primitive_bench',))
