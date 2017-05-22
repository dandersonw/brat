#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import argparse
import diff_and_mark
from sys import path as sys_path
import os.path


try:
    import annotation
except ImportError:
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))


def find_discontinuous(text_annotation):
    return [e for e in text_annotation.get_entities() if len(e.spans) > 1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find entities with discontinuous spans")
    ap.add_argument("dir")
    args = ap.parse_args()

    files = []
    errors = []
    diff_and_mark.add_files(files, args.dir, errors)

    total_entities = 0
    discontinuous_entity_counts = []
    for f in files:
        text_annotation = annotation.TextAnnotations(f)
        total_entities += len(list(text_annotation.get_entities()))
        discontinuous_entities = len(find_discontinuous(text_annotation))
        discontinuous_entity_counts.append(discontinuous_entities)

    total_discontinous_entities = sum(discontinuous_entity_counts)
    print "Total number of entities: %d" % total_entities
    print "Total number of discontinous entites: %d" % total_discontinous_entities


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
