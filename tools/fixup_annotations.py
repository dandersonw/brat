#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import sys
import logging
logging.basicConfig(level=logging.DEBUG)


def remove_discontinuous_entities(doc):
    to_remove = [e for e in doc.entities if len(e.spans) > 1]
    debug("{} discontinuous entities to remove".format(len(to_remove)), doc)
    for entity in to_remove:
        doc.remove_entity(entity, force_remove_relations=True)


def remove_other_relations(doc):
    to_remove = []
    for relation in doc.relations:
        if relation.type == "other_relation":
            to_remove.append(relation)
    for relation in to_remove:
        doc.remove_relation(relation)
    debug("{} `other_relation's to fixup".format(len(to_remove)), doc)
    return doc


def trim_leading_determiners(doc):
    count = 0
    for entity in doc.entities:
        start_token = doc[entity.spans[0][0]]
        # `is_oov' is included because empirically spaCy will tag some valid
        # entities as determiners if their surface forms are OOV
        if start_token.tag_ == "DT" and not start_token.is_oov:
            count += 1
            trim_entity(doc, entity, 0, 1, 0)
    debug("{} leading determiners to fixup".format(count), doc)
    return doc


def trim_punctuation(doc):
    count = 0
    for entity in doc.entities:
        start_token = doc[entity.spans[0][0]]
        end_token = doc[entity.spans[-1][1] - 1]
        if is_trimmable_punctuation(start_token):
            trim_entity(doc, entity, 0, 1, 0)
        if is_trimmable_punctuation(end_token):
            trim_entity(doc, entity, -1, 0, -1)
    debug("{} leading/trailing pieces of punctuation to fixup".format(count), doc)
    return doc


def is_trimmable_punctuation(token):
    GOOD_PUNCT_TAGS = {"-LRB-", "-RRB-"}
    return not token.is_oov and token.pos_ == "PUNCT" and token.tag_ not in GOOD_PUNCT_TAGS


def internal_heads(tokens):
    heads = {}
    new = {tokens}
    while len(new) != len(heads):
        heads = new
        new = {t.head if t.head in tokens else t for t in heads}
    return heads


def external_heads(tokens):
    return {t.head for t in tokens if t.head not in tokens}


def fixup_overlapping_annotations(doc):
    overlapping = ai2_common.find_overlapping(doc)
    for pair in overlapping:
        if pair[0].get_relations() and not pair[1].get_relations():
            remove = pair[1]
        elif pair[1].get_relations() and not pair[0].get_relations():
            remove = pair[0]
        elif len(pair[0]) < len(pair[1]):
            remove = pair[0]
        else:
            remove = pair[1]
        doc.remove_entity(remove, force_remove_relations=True)
    debug("{} overlapping pairs to fixup".format(len(overlapping), doc))
    return doc


def trim_entity(doc, entity, span_idx, left_trim, right_trim):
    span = entity.spans[span_idx]
    span = (span[0] + left_trim, span[1] + right_trim)
    if span[1] - span[0] <= 0:
        if len(entity.spans) == 1:
            warn(u"Removing entity {} that was fully trimmed".format(entity), doc)
            doc.remove_entity(entity, force_remove_relations=True)
        else:
            entity.set_spans(entity.spans[1:])
    spans = entity.spans
    spans[span_idx] = span
    entity.set_spans(spans)


def debug(message, doc):
    logging.debug("{}: {}".format(doc.document_id, message))


def warn(message, doc):
    logging.warn("{}: {}".format(doc.document_id, message))


FIXUP_STEPS = [remove_other_relations,
               remove_discontinuous_entities,
               trim_leading_determiners,
               trim_punctuation,
               fixup_overlapping_annotations]


def fixup(doc):
    for step in FIXUP_STEPS:
        doc = step(doc)
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--outputPath")
    args = parser.parse_args()

    docs = ai2_common.get_docs(*args.paths)
    fixed = [fixup(doc) for doc in docs]

    if args.outputPath is not None:
        for doc in fixed:
            print unicode(doc.brat_annotation)


if __name__ == "__main__":
    main()
