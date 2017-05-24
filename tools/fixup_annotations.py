#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import sys


def fixup_overlapping_annotations(doc):
    overlapping = ai2_common.find_overlapping(doc)
    for pair in overlapping:
        a = pair[0].brat_annotation
        b = pair[1].brat_annotation
        remove = None
        if a.contains(b):
            remove = pair[1]
        elif b.contains(a):
            remove = pair[0]
        else:
            sys.stderr.write("Can't fix the pair of {} in fixup_overlapping_annotations".format(pair))

        if remove is not None:
            doc.remove_entity(remove)
    return doc


FIXUP_STEPS = [fixup_overlapping_annotations]


def fixup(doc):
    for step in FIXUP_STEPS:
        doc = step(doc)
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    docs = ai2_common.get_docs(*args.paths)
    fixed = [fixup(doc) for doc in docs]

    for doc in fixed:
        print unicode(doc.brat_annotation)


if __name__ == "__main__":
    main()
