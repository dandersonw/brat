#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import logging
import re
import os
import os.path


def remove_discontinuous_entities(doc):
    to_remove = [e for e in doc.entities if len(e.spans) > 1]
    debug("{} discontinuous entities to remove".format(len(to_remove)), doc)
    for entity in to_remove:
        doc.remove_entity(entity, force_remove_relations=True)
    return doc


def remove_other_relations(doc):
    """Removes relations of type 'other_relation'."""
    to_remove = []
    for relation in doc.relations:
        if relation.type == "other_relation":
            to_remove.append(relation)
    for relation in to_remove:
        doc.remove_relation(relation)
    debug("{} `other_relation's to remove".format(len(to_remove)), doc)
    return doc


def trim_leading_determiners(doc):
    count = 0
    for entity in doc.entities:
        start_token = doc[entity.spans[0][0]]
        # `is_oov' is included because empirically spaCy will tag some valid
        # entities as determiners if their surface forms are OOV
        if start_token.tag_ == "DT" and not start_token.is_oov:
            count += 1
            adjust_entity_span(doc, entity, 0, 1, 0)
    debug("{} leading determiners to fixup".format(count), doc)
    return doc


def trim_punctuation(doc):
    count = 0
    for entity in doc.entities:
        start_token = doc[entity.spans[0][0]]
        end_token = doc[entity.spans[-1][1] - 1]
        if is_trimmable_punctuation(start_token):
            adjust_entity_span(doc, entity, 0, 1, 0)
        if is_trimmable_punctuation(end_token):
            adjust_entity_span(doc, entity, -1, 0, -1)
    debug("{} leading/trailing pieces of punctuation to fixup".format(count), doc)
    return doc


def merge_acronyms(doc):
    """Merges two entities together if they are connected by a relation commented
    with "equivalent" and one of them looks like an acronym

    """
    relations = doc.relations
    count = 0
    for relation in relations:
        equivalent_relation = [c for c in relation.get_comments() if c.tail.strip() == "equivalent"]
        acronym = looks_like_an_acronym(relation.arg1) or looks_like_an_acronym(relation.arg2)
        if equivalent_relation and acronym:
            merge_entities(relation.arg1, relation.arg2, doc)
            if doc[relation.arg1.spans[-1][1]].tag_ == "-RRB-":
                adjust_entity_span(doc, relation.arg1, -1, 0, 1)
            doc.remove_relation(relation)
            count += 1
    debug("{} acronym annotations merged".format(count), doc)
    return doc


def is_trimmable_punctuation(token):
    GOOD_PUNCT_TAGS = {"-LRB-", "-RRB-"}
    return not token.is_oov and token.pos_ == "PUNCT" and token.tag_ not in GOOD_PUNCT_TAGS


def looks_like_an_acronym(entity):
    ACRONYM_RE = re.compile(r"^[^a-z]+$")
    return min([ACRONYM_RE.search(t.text) is not None for t in entity.get_tokens()])


def fixup_overlapping_annotations(doc):
    """Ensures that there is no token included in two entities."""
    overlapping = ai2_common.find_overlapping(doc)
    for pair in overlapping:
        if doc.get_entity(pair[0].id) is None or doc.get_entity(pair[1].id) is None:
            # We've already removed one of the pair
            continue
        if pair[0].get_relations() and not pair[1].get_relations():
            remove = pair[1]
        elif pair[1].get_relations() and not pair[0].get_relations():
            remove = pair[0]
        elif len(pair[0]) < len(pair[1]):
            remove = pair[0]
        else:
            remove = pair[1]
        doc.remove_entity(remove, force_remove_relations=True)
    debug("{} overlapping pairs to fixup".format(len(overlapping)), doc)
    return doc


def adjust_entity_span(doc, entity, span_idx, left_adjustment, right_adjustment):
    """Moves the boundaries of one span of an entity.

    The leftward boundary of the 'span_idx'th span is moved by 'left_adjustment' and
    the rightword boundary by 'right_adjustment'. If negative/positive this causes the
    entity to grow.

    """
    span = entity.spans[span_idx]
    span = (span[0] + left_adjustment, span[1] + right_adjustment)
    if span[1] - span[0] <= 0:
        if len(entity.spans) == 1:
            warn(u"Removing entity {} that was fully trimmed".format(entity), doc)
            doc.remove_entity(entity, force_remove_relations=True)
        else:
            entity.set_spans(entity.spans[1:])
    spans = entity.spans
    spans[span_idx] = span
    entity.set_spans(spans)


def merge_entities(a, b, doc):
    """Merge entity b into entity a"""
    for relation in b.get_relations():
        relation.swap(b, a)
    # Let's not deal with discontinuous entities here
    assert len(a.spans) == 1 and len(b.spans) == 1
    l = min(a.spans[0][0], b.spans[0][0])
    r = max(a.spans[0][1], b.spans[0][1])
    a.set_spans([(l, r)])
    doc.remove_entity(b, force_remove_relations=False)


def debug(message, doc):
    logging.debug("{}: {}".format(doc.document_id, message))


def warn(message, doc):
    logging.warn("{}: {}".format(doc.document_id, message))


FIXUP_STEPS = [merge_acronyms,
               remove_other_relations,
               trim_leading_determiners,
               trim_punctuation,
               fixup_overlapping_annotations]


def fixup(doc):
    for step in FIXUP_STEPS:
        doc = step(doc)
    return doc


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--outputPath")
    args = parser.parse_args()

    docs = ai2_common.get_docs(*args.paths)
    fixed = [fixup(doc) for doc in docs]

    if args.outputPath is not None:
        if not os.path.exists(args.outputPath):
            os.mkdir(args.outputPath)
        for doc in fixed:
            doc.write_to_path(args.outputPath)


if __name__ == "__main__":
    main()
