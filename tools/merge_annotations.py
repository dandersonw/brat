#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import copy
import locale
import logging
import itertools
import codecs
import os.path
import sys
from shutil import copyfile
from collections import defaultdict

try:
    import annotation
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation


def suffix_annotation_id(prefix, ann):
    ann = copy.copy(ann)
    ann.id = "{}.{}".format(ann.id, prefix)
    return ann


def prefix_annotation_type(ann, prefix):
    ann = copy.copy(ann)
    ann.type = prefix + ann.type
    return ann


def set_annotation_type(ann, type):
    ann = copy.copy(ann)
    ann.type = type
    return ann


def get_annotator(brat):
    return os.path.basename(os.path.dirname(brat.get_document()))


def get_annotator_brats(annotator_dirs, identifier):
        annotators_brat = dict()
        for dir in annotator_dirs:
            annotator = os.path.basename(dir)
            annotators_brat[annotator] = annotation.TextAnnotations(os.path.join(dir, identifier))
        return annotators_brat


def create_correction_file(identifier, correction_dir, annotator_dirs):
    annotator_dir = annotator_dirs[0]
    copyfile(os.path.join(annotator_dir, identifier + ".txt"),
             os.path.join(correction_dir, identifier + ".txt"))
    correction_ann = os.path.join(correction_dir, identifier + ".ann")
    codecs.open(correction_ann, mode="w").close()
    return correction_ann


def merge_annotations(identifier, correction_dir, annotator_dirs):
    """Combines the brat annotations for 'identifier' from each dir in 'annotator_dirs'.

    Overwrites any existing file in 'correction_dir'.

    Works according to the scheme laid out in:
    docs.google.com/document/d/1zj5WAAykZfrPJwaKtv-AUD0m9BrVH6ybcl17PunnIgc

    It is a significant invariant that there will only be one entity with any
    given set of spans.

    """
    annotator_brats = get_annotator_brats(annotator_dirs, identifier)
    annotators = annotator_brats.keys()
    brats = annotator_brats.values()
    correction_file = create_correction_file(identifier,
                                             correction_dir,
                                             annotator_dirs)
    corrected = annotation.TextAnnotations(os.path.join(correction_dir, identifier))

    all_entities = itertools.chain.from_iterable(
        (((e, b) for e in b.get_entities()) for b in brats))
    accounted_for = set()
    no_perfect_match = []

    # Entities with perfect span matches
    for (entity, from_brat) in all_entities:
        if entity in accounted_for:
            continue
        matches = get_entity_matches(entity, brats)
        accounted_for.update(set(matches))
        if len(matches) < len(annotators):
            no_perfect_match.append((entity, from_brat))
        else:
            ann = suffix_annotation_id(get_annotator(from_brat), entity)
            types = set((e.type for e in matches))
            if len(types) > 1:
                # Type of the entity is contested
                ann = set_annotation_type(ann, "FIX_TYPE")
            corrected.add_annotation(ann)

    for (entity, from_brat) in no_perfect_match:
        id_prefixed = suffix_annotation_id(get_annotator(from_brat), entity)
        if len(get_entity_overlaps(entity, brats)) > 1:
            # With some overlap (other than itself)
            ann = prefix_annotation_type(id_prefixed, "FIX_SPAN_")
        else:
            # With no overlap
            ann = prefix_annotation_type(id_prefixed, "VERIFY_")
        corrected.add_annotation(ann)

    # Transfer comments on entities
    for entity in corrected.get_entities():
        transfer_comments(corrected, entity, brats)

    all_relations = itertools.chain.from_iterable(
        (((r, b) for r in b.get_relations()) for b in brats))
    accounted_for = set()
    no_perfect_match = []

    # Relations for which the arguments have perfect span matches
    for (relation, from_brat) in all_relations:
        if relation in accounted_for:
            continue
        matches = get_relation_matches(relation, from_brat, brats)
        accounted_for.update(set(matches))
        if len(matches) < len(annotators):
            no_perfect_match.append((relation, from_brat))
        else:
            # Relation needs to refer to entities in the new set
            ann = translate_relation(relation, from_brat, corrected)
            ann = suffix_annotation_id(get_annotator(from_brat), ann)
            types = set((r.type for r in matches))
            if len(types) > 1:
                # Type of the relation is contested
                ann = set_annotation_type(ann, "FIX_RELATION_TYPE")
            corrected.add_annotation(ann)

    for (relation, from_brat) in no_perfect_match:
        ann = prefix_annotation_type(
            suffix_annotation_id(get_annotator(from_brat),
                                 translate_relation(relation, from_brat, corrected)),
            "VERIFY_")
        corrected.add_annotation(ann)

    with codecs.open(correction_file, mode="w", encoding="utf-8") as outputFile:
        outputFile.write(unicode(corrected))


def translate_relation(relation, from_brat, to_brat):
    """Finds entities in 'to_brat' that have the same spans as the args to
    'relation' in 'from_brat' and replaces them in 'relation'.

    """
    arg1 = from_brat.get_ann_by_id(relation.arg1)
    arg2 = from_brat.get_ann_by_id(relation.arg2)
    arg1_match = get_entity_matches(arg1, [to_brat])
    arg2_match = get_entity_matches(arg2, [to_brat])
    assert arg1_match and arg2_match
    relation = copy.copy(relation)
    relation.arg1 = arg1_match[0].id
    relation.arg2 = arg2_match[0].id
    return relation


def transfer_comments(to_brat, entity, from_brats):
    for brat in from_brats:
        entities = set(brat.get_entities())
        for c in brat.get_oneline_comments():
            target = brat.get_ann_by_id(c.target)
            if target in entities and target.same_span(entity):
                c = copy.copy(c)
                c.target = entity.id
                to_brat.add_annotation(c)


def is_annotation_contested(annotation):
    prefixes = ["FIX_", "VERIFY_"]
    return max((annotation.type.startswith(p) for p in prefixes))


def get_relation_matches(relation, from_brat, brats):
    """Finds relations that have arguments which match on a span basis."""
    arg1 = from_brat.get_ann_by_id(relation.arg1)
    arg2 = from_brat.get_ann_by_id(relation.arg2)
    matches = []
    for brat in brats:
        for r2 in brat.get_relations():
            o_arg1 = brat.get_ann_by_id(r2.arg1)
            o_arg2 = brat.get_ann_by_id(r2.arg2)
            if arg1.same_span(o_arg1) and arg2.same_span(o_arg2):
                matches.append(r2)
    return matches


def get_entity_matches(entity, brats):
    """Finds entities which match on a span basis."""
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if entity.same_span(e2):
                matches.append(e2)
                break
    return matches


def get_entity_overlaps(entity, brats):
    """Finds entities which overlap."""
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if ai2_common.any_overlapping_spans(entity, e2):
                matches.append(e2)
    return matches


def get_comments(brat, ann):
    return [c for c in brat.get_oneline_comments() if c.target == ann.id]


def merge(args):
    """Call 'merge_annotations' for each identifier found in the provided annotator
    directories, each with the set of annotator directories that it is found
    in.

    """
    # Annotator names will derived from the basenames so make sure they don't
    # end with a separator
    args.annotator_dirs = [os.path.normpath(d) for d in args.annotator_dirs]
    args.correction_dir = os.path.normpath(args.correction_dir)

    if not os.path.exists(args.correction_dir):
        os.mkdir(args.correction_dir)

    identifiers_annotators = defaultdict(list)
    for dir in args.annotator_dirs:
        identifiers = (os.path.basename(os.path.normpath(i))
                       for i in ai2_common.get_identifiers(dir))
        for identifier in identifiers:
            identifiers_annotators[identifier].append(dir)

    for (identifier, dirs) in identifiers_annotators.items():
        if len(dirs) < len(args.annotator_dirs):
            logging.warn("Only {} annotators have annotated {}".format(len(dirs), identifier))
        merge_annotations(identifier, args.correction_dir, dirs)


def verify(args):
    """Verify that there are no contested annotations remaining"""
    identifiers = ai2_common.get_identifiers(args.correction_dir)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    not_finished = []
    for identifier in identifiers:
        unresolved = []
        brat = annotation.TextAnnotations(identifier)
        for a in brat:
            if isinstance(a, annotation.TypedAnnotation):
                if is_annotation_contested(a):
                    unresolved.append(a)
        logging.debug("{} has {} unresolved conflicts".format(identifier, len(unresolved)))
        if unresolved:
            not_finished.append((identifier, unresolved))

    if not_finished:
        logging.warn("{} files with unresolved annotations".format(len(not_finished)))
        sys.exit(1)


def main():
    locale.setlocale(locale.LC_ALL, "")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("correction_dir")

    create_parser = subparsers.add_parser("merge", parents=[common_parser])
    create_parser.add_argument("annotator_dirs", nargs="+")
    create_parser.set_defaults(func=merge)

    verify_parser = subparsers.add_parser("verify", parents=[common_parser])
    verify_parser.add_argument("--verbose",
                               help="Print information about individual files",
                               action="store_true")
    verify_parser.set_defaults(func=verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
