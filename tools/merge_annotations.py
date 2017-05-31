#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

import ai2_common
import argparse
import curses
import time
import locale
import itertools
import intervaltree

locale.setlocale(locale.LC_ALL, "")


class MergeHistory:
    def __init__(self, logfile):
        self.logfile = logfile


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


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
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


if __name__ == "__main__":
    main()
