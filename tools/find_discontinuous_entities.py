#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import argparse
import diff_and_mark
from sys import path as sys_path
import os.path
import itertools
import codecs
import sys

UTF8Writer = codecs.getwriter('utf8')
sys.stdout = UTF8Writer(sys.stdout)


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


def print_entity_mention(entity, source_text):
    sys.stdout.write("\n" + "-" * 10 + "\n")
    WINDOW = 20
    GREEN = "\033[0;32m"
    END_COLOR = "\033[0;0m"
    leftmost = max(0, min(itertools.chain.from_iterable(entity.spans)) - WINDOW)
    rightmost = min(len(source_text), max(itertools.chain.from_iterable(entity.spans)) + WINDOW)
    i = leftmost
    for span in entity.spans:
        sys.stdout.write(source_text[i: span[0]])
        sys.stdout.write(GREEN)
        sys.stdout.write(source_text[span[0]: span[1]])
        sys.stdout.write(END_COLOR)
        i = span[1]

    sys.stdout.write(source_text[i:rightmost])
    sys.stdout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find entities with discontinuous spans")
    ap.add_argument("dir")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = []
    errors = []
    diff_and_mark.add_files(files, args.dir, errors)

    total_entities = 0
    discontinuous_entity_counts = []
    for f in files:
        text_annotation = annotation.TextAnnotations(f)
        entity_count = len(list(text_annotation.get_entities()))
        discontinuous = find_discontinuous(text_annotation)
        discontinuous_count = len(discontinuous)
        total_entities += entity_count
        discontinuous_entity_counts.append(discontinuous_count)
        if args.verbose:
            if total_entities == 0 or discontinuous_count == 0:
                continue
            print "\n" + "-" * 60
            print "{} discontinous entities out of {} in {}".format(discontinuous_count, entity_count, f)
            for e in discontinuous:
                print_entity_mention(e, text_annotation.get_document_text())

    total_discontinuous_entities = sum(discontinuous_entity_counts)
    print "Total number of entities: {}".format(total_entities)
    print "Total number of discontinous entites: {}".format(total_discontinuous_entities)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
