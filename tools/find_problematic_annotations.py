#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import argparse
import diff_and_mark
import ai2_common
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


def find_overlapping(text_annotation):
    return filter(lambda c: ai2_common.any_overlapping_spans(c[0], c[1]),
                  itertools.combinations(text_annotation.get_entities(), 2))


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

    sys.stdout.write(source_text[i: rightmost])
    sys.stdout.flush()


def print_overlapping_entity_mentions(a, b, source_text):
    sys.stdout.write("\n" + "-" * 10 + "\n")
    WINDOW = 20
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[1;34m"
    END_COLOR = "\033[0;0m"
    leftmost = max(0, min(itertools.chain.from_iterable(a.spans + b.spans)) - WINDOW)
    rightmost = min(len(source_text), max(itertools.chain.from_iterable(a.spans + b.spans)) + WINDOW)

    b_len = len(b.spans)
    a_len = len(a.spans)
    i = leftmost
    a_idx = 0
    b_idx = 0
    while a_idx < a_len or b_idx < b_len:
        j = min(a.spans[a_idx][0], b.spans[b_idx][0])
        sys.stdout.write(source_text[i: j])
        i = j
        if b_idx == b_len or a.spans[a_idx][0] < b.spans[b_idx][0]:
            sys.stdout.write(YELLOW)
            j = min(a.spans[a_idx][1], b.spans[b_idx][0])
            sys.stdout.write(source_text[i: j])
            i = j
        elif a_idx == a_len or b.spans[b_idx][0] < a.spans[a_idx][0]:
            sys.stdout.write(BLUE)
            j = min(b.spans[b_idx][1], a.spans[a_idx][0])
            sys.stdout.write(source_text[i: j])
            i = j
        else:
            sys.stdout.write(GREEN)
            j = min(a.spans[a_idx][1], b.spans[b_idx][1])
            sys.stdout.write(source_text[i: j])
            i = j
        sys.stdout.write(END_COLOR)
        while (a_idx < a_len and i > a.spans[a_idx][0]) or (b_idx < b_len and i > b.spans[b_idx][0]):
            if a_idx < a_len and i > a.spans[a_idx][0]:
                if i == a.spans[a_idx][1]:
                    a_idx += 1
                else:
                    j = min(b.spans[b_idx][1], a.spans[a_idx][1])
                    sys.stdout.write(GREEN)
                    sys.stdout.write(source_text[i: j])
                    i = j
                sys.stdout.write(END_COLOR)

            if b_idx < b_len and i > b.spans[b_idx][0]:
                if i == b.spans[b_idx][1]:
                    b_idx += 1
                else:
                    j = min(b.spans[b_idx][1], a.spans[a_idx][1])
                    sys.stdout.write(GREEN)
                    sys.stdout.write(source_text[i: j])
                    i = j
                sys.stdout.write(END_COLOR)
    sys.stdout.write(source_text[i: rightmost])
    sys.stdout.flush()


def display_discontinuous(files, verbose):
    total_entities = 0
    discontinuous_entity_counts = []
    for f in files:
        text_annotation = annotation.TextAnnotations(f)
        entity_count = len(list(text_annotation.get_entities()))
        discontinuous = find_discontinuous(text_annotation)
        discontinuous_count = len(discontinuous)
        total_entities += entity_count
        discontinuous_entity_counts.append(discontinuous_count)
        if verbose:
            if total_entities == 0 or discontinuous_count == 0:
                continue
            print "\n" + "-" * 60
            print "{} discontinous entities out of {} in {}".format(discontinuous_count, entity_count, f)
            for e in discontinuous:
                print_entity_mention(e, text_annotation.get_document_text())

    total_discontinuous_entities = sum(discontinuous_entity_counts)
    print "Total number of entities: {}".format(total_entities)
    print "Total number of discontinous entites: {}".format(total_discontinuous_entities)


def display_overlapping(files, verbose):
    total_entities = 0
    overlapping_entity_counts = []
    for f in files:
        text_annotation = annotation.TextAnnotations(f)
        entity_count = len(list(text_annotation.get_entities()))
        overlapping = find_overlapping(text_annotation)
        overlapping_count = len(overlapping)
        total_entities += entity_count
        overlapping_entity_counts.append(overlapping_count)
        if verbose:
            if total_entities == 0 or overlapping_count == 0:
                continue
            print "\n" + "-" * 60
            print "{} overlapping pairs out of {} entities in {}".format(overlapping_count, entity_count, f)
            for e in overlapping:
                print_overlapping_entity_mentions(e[0], e[1], text_annotation.get_document_text())

    total_overlapping_entities = sum(overlapping_entity_counts)
    print "Total number of entities: {}".format(total_entities)
    print "Total number of overlapping entites: {}".format(total_overlapping_entities)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find entities with discontinuous spans")
    ap.add_argument("dir")
    ap.add_argument("category")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = []
    errors = []
    diff_and_mark.add_files(files, args.dir, errors)

    if args.category == "discontinuous":
        display_discontinuous(files, args.verbose)
    elif args.category == "overlapping":
        display_overlapping(files, args.verbose)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
