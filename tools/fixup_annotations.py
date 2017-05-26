#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import sys
import logging
logging.basicConfig(level=logging.DEBUG)


def remove_other_relations(doc):
    to_remove = []
    for relation in doc.relations:
        if relation.type == "other_relation":
            to_remove.append(relation)
    logging.debug("{} `other_relation's to fixup in doc {}".format(len(to_remove), doc.document_id))
    for relation in to_remove:
        doc.remove_relation(relation)
    return doc


def fixup_overlapping_annotations(doc):
    overlapping = ai2_common.find_overlapping(doc)
    logging.debug("{} overlapping pairs to fixup in doc {}".format(len(overlapping), doc.document_id))
    for pair in overlapping:
        if pair[0].get_relations() and not pair[1].get_relations():
            remove = pair[1]
        elif pair[1].get_relations() and not pair[0].get_relations():
            remove = pair[0]
        elif len(pair[0]) < len(pair[1]):
            remove = pair[0]
        else:
            remove = pair[1]
        doc.remove_entity(remove)
    return doc


FIXUP_STEPS = [remove_other_relations,
               fixup_overlapping_annotations]


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
