#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import curses
import time
import locale
import itertools
import intervaltree
import json
import codecs
import os.path


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
        self.identifier = identifier
        self.correction_dir = correction_dir
        self.annotator_dirs = annotator_dirs
        self.accepted = []
        self.rejected = []

    def write_logfile(self):
        config = {"identifier": self.identifier,
                  "correction_dir": self.correction_dir,
                  "annotator_dirs": self.annotator_dirs}
        with codecs.open(self.logfile, mode="w", encoding="utf-8") as outputFile:
            json.dump(config, outputFile)
            outputFile.write("\n")


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


def init_merge(args):
    logfile = os.path.join(args.logfile_dir, args.identifier + ".mrg")
    if os.path.exists(logfile):
        raise ValueError("Logfile already exists!")
    history = MergeHistory(logfile)
    history.init(args.identifier, args.correction_dir, args.annotator_dirs)
    history.write_logfile()


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

    init_parser = subparsers.add_parser("init", parents=[common])
    init_parser.add_argument("identifier")
    init_parser.add_argument("correction_dir", nargs=1)
    init_parser.add_argument("annotator_dirs", nargs="+")
    init_parser.set_defaults(func=init_merge)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
