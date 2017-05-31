#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import copy
import locale
import itertools
import intervaltree
import codecs
import os.path
import sys
from shutil import copyfile

try:
    import annotation
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation


def prefix_annotation(prefix, ann):
    new_id = "{}-{}".format(prefix, ann.id)
    ann = copy.copy(ann)
    ann.id = new_id
    id_attrs = ["target", "arg1", "arg2"]
    for attr in id_attrs:
        if hasattr(ann, attr):
            setattr(ann, attr, "{}-{}".format(prefix, getattr(ann, attr)))


def get_annotator_brats(annotator_dirs, identifier):
        annotators_brat = dict()
        for dir in annotator_dirs:
            annotator = os.path.basename(dir)
            annotators_brat[annotator] = annotation.TextAnnotations(os.path.join(dir, identifier))
        return annotators_brat


def get_entity_span_tree(doc):
    entspans = list(itertools.chain.from_iterable((((s[0], s[1], e)
                                                    for s in e.spans)
                                                   for e in doc.entities)))
    return intervaltree.IntervalTree.from_tuples(entspans)


def logfile_path(dir, identifier):
    return os.path.join(dir, identifier + ".mrg")


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

    all_entities = itertools.chain.from_iterable((k.get_entities() for k in brats))
    unresolved = []

    # Entities with perfect span matches
    for entity in all_entities:
        matches = get_entity_matches(entity, brats)
        in_already = get_entity_matches(entity, [corrected])
        if len(in_already) > 0:
            continue
        elif len(matches) < len(annotators):
            unresolved.append(entity)
        else:
            types = set((e.type for e in matches))
            if len(types) == 1:
                etype = list(types)[0]
            else:
                # TODO - resolve type disagreement with a different policy?
                etype = "Entity"
            entity.type = etype
            # TODO prefix by anything?
            corrected.add_annotation(entity)

    
    
    with codecs.open(correction_file, mode="w", encoding="utf-8") as outputFile:
        outputFile.write(unicode(corrected))


def get_entity_matches(entity, brats):
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if entity.same_span(e2):
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
