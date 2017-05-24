#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse

FIXUP_STEPS = []


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
