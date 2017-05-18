#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

from __future__ import with_statement
from scipy import stats
import argparse
import itertools


'''
Compute inter-annotator agreement
'''

try:
    import annotation
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))


class Agreement:
    def __init__(self, annotations):
        self.annotations = annotations

    def exact_match_score(self):
        total = 0
        count = 0
        for combination in itertools.combinations(self.annotations, 2):
            total += self.f1(combination[0], combination[1])
            count += 1
        return total / count

    def f1(self, gold, notGold):
        precision = self.precision(gold, notGold)
        recall = self.recall(gold, notGold)
        return stats.hmean([precision, recall])

    def precision(self, gold, notGold):
        entities = list(notGold.get_entities())
        found = filter(lambda e: self.find_entity(gold, e) is not None, entities)
        return float(len(found)) / len(entities)

    def recall(self, gold, notGold):
        entities = list(gold.get_entities())
        found = filter(lambda e: self.find_entity(notGold, e) is not None, entities)
        return float(len(found)) / len(entities)

    def find_entity(self, haystack, needle):
        for entity in haystack.get_entities():
            if entity.same_span(needle) and entity.type == needle.type:
                return entity
        return None


def calculate_agreement(files):
    annotations = map(lambda f: annotation.TextAnnotations(f), files)
    agreement = Agreement(annotations)
    print agreement.exact_match_score()


def argparser():
    ap = argparse.ArgumentParser(description="Calculate inter-annotator agreement")
    ap.add_argument("first")
    ap.add_argument("second")
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv
    args = argparser().parse_args(argv[1:])

    calculate_agreement([args.first, args.second])


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
