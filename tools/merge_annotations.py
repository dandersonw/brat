#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import copy
import curses
import time
import locale
import itertools
import intervaltree
import json
import codecs
import os.path
import sys
from shutil import copyfile

try:
    import annotation
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation


class MergeHistory:
    def __init__(self, logfile):
        self.logfile = logfile
        if os.path.exists(logfile):
            with codecs.open(logfile, mode="r", encoding="utf-8") as inputFile:
                lines = list(inputFile)
                config = json.loads(lines[0].strip())
                self.identifier = config["identifier"]
                self.correction_dir = config["correction_dir"]
                self.annotator_dirs = config["annotator_dirs"]
                self.accepted = []
                self.rejected = []
                for line in lines[1:]:
                    tokens = line.split("t")
                    action = tokens[0]
                    if action == "ACCEPT":
                        self.accepted.append(tuple(tokens[1:]))
                    elif action == "REJECT":
                        self.rejected.append(tuple(tokens[1:]))
                    else:
                        raise ValueError("Unrecognized line in logfile:\n{}".format(line))
        else:
            # Need to call `init' to get fields initialized with their values
            pass

    def init(self, identifier, correction_dir, annotator_dirs):
        if not annotator_dirs:
            raise ValueError("Must provide at least one annotator!")

        self.identifier = identifier
        self.correction_dir = correction_dir
        self.annotator_dirs = annotator_dirs
        self.accepted = []
        self.rejected = []

        annotator_dir = annotator_dirs[0]
        copyfile(os.path.join(annotator_dir, identifier + ".txt"),
                 os.path.join(correction_dir, identifier + ".txt"))
        open(os.path.join(correction_dir, identifier + ".ann"), mode="w").close()

    def build_corrected_brat(self):
        brat = annotation.TextAnnotations(os.path.join(self.correction_dir, self.identifier))
        annotators_brat = self.get_annotator_brats()
        for a in self.accepted:
            annotator = a[0]
            annotation_id = a[1]
            ann = annotators_brat[annotator].get_ann_by_id(annotation_id)
            ann = prefix_annotation(annotator, ann)
            brat.add_annotation(ann)
        # call sanity checking?
        return brat

    def get_annotator_brats(self):
        annotators_brat = dict()
        for dir in self.annotator_dirs:
            annotator = os.path.basename(dir)
            annotators_brat[annotator] = annotation.TextAnnotations(os.path.join(dir,
                                                                                 self.identifier))
        return annotators_brat

    def write_logfile(self):
        config = {"identifier": self.identifier,
                  "correction_dir": self.correction_dir,
                  "annotator_dirs": self.annotator_dirs}
        with codecs.open(self.logfile, mode="w", encoding="utf-8") as outputFile:
            json.dump(config, outputFile)
            outputFile.write("\n")
            for a in self.accepted:
                outputFile.write("\t".join(tuple(["ACCEPT"]) + a + "\n"))
            for r in self.rejected:
                outputFile.write("\t".join(tuple(["REJECT"]) + a + "\n"))


def prefix_annotation(prefix, ann):
    new_id = "{}-{}".format(prefix, ann.id)
    ann = copy.copy(ann)
    ann.id = new_id
    id_attrs = ["target", "arg1", "arg2"]
    for attr in id_attrs:
        if hasattr(ann, attr):
            setattr(ann, attr, "{}-{}".format(prefix, getattr(ann, attr)))


def run(stdscr, args):
    doc = ai2_common.load_doc("../data/craft/kevin/last")
    display_doc(stdscr, doc, 0, green_if_entity(doc))
    time.sleep(10)


def display_doc(scr, doc, offset, attr_function):
    height, width = scr.getmaxyx()
    text = doc.document_text
    i = offset
    f = doc[i].idx
    cy, cx = scr.getyx()
    curses.flash()
    while i < len(doc) and cy < height - 2:
        t = doc[i].idx + len(doc[i])
        scr.addstr(text[f:t], attr_function(i))
        f = t
        i += 1
        cy, cx = scr.getyx()
    scr.refresh()


def green_if_entity(doc):
    tree = get_entity_span_tree(doc)
    return lambda tidx: curses.color_pair(1 if tree[tidx] else 0)


def write_span_attr(scr, height, width, span, attr):
    x = span[0] % width
    y = span[0] / width
    num = span[1] - span[0]
    scr.chgat(y, x, num, attr)


def init_curses():
    curses.noecho()
    curses.cbreak()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)


def get_entity_span_tree(doc):
    entspans = list(itertools.chain.from_iterable((((s[0], s[1], e)
                                                    for s in e.spans)
                                                   for e in doc.entities)))
    return intervaltree.IntervalTree.from_tuples(entspans)


def logfile_path(dir, identifier):
    return os.path.join(dir, identifier + ".mrg")


def init_merge(args):
    logfile = logfile_path(args.logfile_dir, args.identifier)
    if os.path.exists(logfile):
        raise ValueError("Logfile already exists!")
    history = MergeHistory(logfile)
    history.init(args.identifier, args.correction_dir, args.annotator_dirs)
    history.write_logfile()


def automatic_portion(args):
    logfile = logfile_path(args.logfile_dir, args.identifier)
    if not os.path.exists(logfile):
        raise ValueError("Logfile does not exist!")
    history = MergeHistory(logfile)
    annotator_brats = history.get_annotator_brats()
    annotators = annotator_brats.keys()
    brats = annotator_brats.values()
    corrected = history.build_corrected_brat()

    entities = itertools.chain.from_iterable((k.get_entities() for k in brats))
    for entity in entities:
        matches = get_entity_matches(entity, brats)
        in_already = get_entity_matches(entity, corrected)
        if len(in_already) > 0 or len(matches) < len(annotators):
            continue
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
            history.corrected.append(())


def get_entity_matches(entity, brats):
    matches = []
    for brat in brats:
        for e2 in brat.get_entities():
            if entity.same_span(e2):
                matches.append(e2)
                break
    return matches


def display(args):
    stdscr = curses.initscr()
    init_curses()
    stdscr.keypad(1)
    try:
        run(stdscr, args)
    finally:
        stdscr.keypad(0)
        curses.nocbreak()
        curses.echo()
        curses.endwin()


def main():
    locale.setlocale(locale.LC_ALL, "")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("logfile_dir")
    common.add_argument("identifier")

    init_parser = subparsers.add_parser("init", parents=[common])
    init_parser.add_argument("correction_dir")
    init_parser.add_argument("annotator_dirs", nargs="+")
    init_parser.set_defaults(func=init_merge)

    automatic_portion_parser = subparsers.add_parser("auto", parents=[common])
    automatic_portion_parser.set_defaults(func=automatic_portion)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
