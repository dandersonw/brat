#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import copy
import locale
import itertools
import codecs
import os.path
import sys
from shutil import copyfile

try:
    import annotation
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation


def suffix_annotation_id(prefix, ann):
    new_id = "{}.{}".format(ann.id, prefix)
    ann = copy.copy(ann)
    ann.id = new_id
    return ann


def prefix_annotation_type(ann, prefix):
    ann = copy.copy(ann)
    ann.type = prefix + ann.type
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


def automatic_portion(args):
    annotator_brats = get_annotator_brats(args.annotator_dirs, args.identifier)
    annotators = annotator_brats.keys()
    brats = annotator_brats.values()
    correction_file = create_correction_file(args.identifier,
                                             args.correction_dir,
                                             args.annotator_dirs)
    corrected = annotation.TextAnnotations(os.path.join(args.correction_dir, args.identifier))

    all_entities = itertools.chain.from_iterable(
        (((e, b) for e in b.get_entities()) for b in brats))
    accounted_for = set()
    no_perfect_match = []

    # Entities with perfect span matches
    for (entity, from_brat) in all_entities:
        matches = get_entity_matches(entity, brats)
        if len(matches) < len(annotators):
            if entity not in accounted_for:
                no_perfect_match.append((entity, from_brat))
                accounted_for.update(set(matches))
        else:
            ann = suffix_annotation_id(get_annotator(from_brat), entity)
            types = set((e.type for e in matches))
            if len(types) > 1:
                # Type of the entity is contested
                ann = prefix_annotation_type(ann, "FIX_TYPE_")
            corrected.add_annotation(ann)

    for (entity, from_brat) in no_perfect_match:
        id_prefixed = suffix_annotation_id(get_annotator(from_brat), entity)
        if get_entity_overlaps(entity, brats):
            # With some overlap
            ann = prefix_annotation_type(id_prefixed, "FIX_SPAN_")
        else:
            # With no overlap
            ann = prefix_annotation_type(id_prefixed, "VERIFY_")
        corrected.add_annotation(ann)

    all_relations = itertools.chain.from_iterable(
        (((r, b) for r in b.get_relations()) for b in brats))
    accounted_for = set()
    no_perfect_match = []

    # Relations for which the arguments have perfect span matches
    for (relation, from_brat) in all_relations:
        matches = get_relation_matches(relation, from_brat, brats)
        if len(matches) < len(annotators):
            if relation not in accounted_for:
                no_perfect_match.append((relation, from_brat))
                accounted_for.update(set(matches))
        else:
            # Relation needs to refer to entities in the new set
            ann = translate_relation(relation, from_brat, corrected)
            ann = suffix_annotation_id(get_annotator(from_brat), ann)
            types = set((r.type for r in matches))
            if len(types) > 1:
                # Type of the relation is contested
                ann = prefix_annotation_type(ann, "FIX_TYPE_")
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
    arg1 = from_brat.get_ann_by_id(relation.arg1)
    arg2 = from_brat.get_ann_by_id(relation.arg2)
    arg1_match = get_entity_matches(arg1, [to_brat])
    arg2_match = get_entity_matches(arg2, [to_brat])
    assert arg1_match and arg2_match
    relation = copy.copy(relation)
    relation.arg1 = arg1_match[0].id
    relation.arg2 = arg2_match[0].id
    return relation


def is_entity_contested(entity):
    prefixes = ["FIX_TYPE_", "FIX_SPAN_", "VERIFY_"]
    return max((entity.type.startswith(p) for p in prefixes))


def get_relation_matches(relation, from_brat, brats):
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
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if entity.same_span(e2):
                matches.append(e2)
                break
    return matches


def get_entity_overlaps(entity, brats):
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if ai2_common.any_overlapping_spans(entity, e2):
                matches.append(e2)
                break
    return matches


def main():
    locale.setlocale(locale.LC_ALL, "")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("identifier")

    automatic_portion_parser = subparsers.add_parser("auto", parents=[common])
    automatic_portion_parser.add_argument("correction_dir")
    automatic_portion_parser.add_argument("annotator_dirs", nargs="+")
    automatic_portion_parser.set_defaults(func=automatic_portion)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
