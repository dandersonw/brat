#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

from __future__ import with_statement
from scipy import stats
from sys import path as sys_path
from collections import defaultdict
import numpy as np
import argparse
import itertools
import diff_and_mark
import os.path

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))


'''
Compute inter-annotator agreement
'''

try:
    import annotation
except ImportError:
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation


class Agreement:
    def __init__(self, annotations):
        self.annotations = annotations
        self.strict_entity_type = True
        self.strict_relation_type = True
        self.filter_entity_types = None
        self.filter_relation_types = None
        self.strict_entity_offset = True
        self.ignore_discontinuous = True

    def exact_match_score(self):
        total = 0
        count = 0
        groupedByDoc = defaultdict(list)
        for doc in self.annotations:
            groupedByDoc[os.path.basename(doc.get_document())].append(doc)
        for (doc_name, annotations) in groupedByDoc.items():
            for combination in itertools.combinations(annotations, 2):
                total += self.f1(combination[0], combination[1])
                count += 1
        if count == 0:
            print "No document was found that was annotated twice"
            return -1
        return total / count

    def entity_span_fleiss_kappa(self):
        spans = map(lambda e: self.get_entity_spans(e), self.annotations)
        total_len = len(self.annotations[0].get_document_text())
        biluo = map(lambda s: spans_to_biluo(s, total_len), spans)
        category_counts = np.zeros((total_len, 5))
        for annotator in biluo:
            for i in xrange(total_len):
                category_counts[i][annotator[i]] += 1
        return fleiss_kappa(category_counts)

    def get_entity_spans(self, doc):
        return list(itertools.chain.from_iterable(
            [e.spans for e in doc.get_entities() if self.entity_is_included(e)]))

    def f1(self, gold, notGold):
        precision = self.precision(gold, notGold)
        recall = self.recall(gold, notGold)
        if precision == 0 or recall == 0:
            return 0
        return stats.hmean([precision, recall])

    def precision(self, gold, notGold):
        entities = [e for e in notGold.get_entities() if self.entity_is_included(e)]
        if len(entities) == 0:
            return 1
        found = filter(lambda e: self.find_matching_entities(gold, e), entities)
        return float(len(found)) / len(entities)

    def recall(self, gold, notGold):
        return self.precision(notGold, gold)

    def find_matching_entities(self, haystack, needle):
        return [e for e in haystack.get_entities() if self.entities_match(e, needle)]

    def entity_is_included(self, e):
        return ((self.filter_entity_types is None or e in self.filter_entity_types)
                and (self.ignore_discontinuous is False or len(e.spans) == 1))

    def filter_relations(self, relations):
        if self.filter_relation_types is None:
            return relations
        else:
            return filter(lambda r: r.type in self.filter_relation_types, relations)

    def entities_match(self, a, b):
        return (not self.strict_entity_type or a.type == b.type) \
            and ((not self.strict_entity_offset and self.any_overlapping_spans(a, b))
                 or a.same_span(b))

    def any_overlapping_spans(self, a, b):
        for i in a.spans:
            for j in b.spans:
                if j[0] < i[1] and i[0] < j[1]:
                    return True
        return False


def spans_to_biluo(spans, total_len):
    # o -> 0, b -> 1, i -> 2, l -> 3, u -> 4
    spans = sorted(spans)
    result = [0] * total_len
    i = 0
    j = 0
    while j < len(spans):
        if i >= total_len:
            print spans
        if i < spans[j][0]:  # o
            result[i] = 0
        elif i == spans[j][0] and (i + 1 < spans[j][1]):  # b
            result[i] = 1
        elif i == spans[j][0]:  # u
            result[i] = 4
            j += 1
        elif i + 1 == spans[j][1]:  # l
            result[i] = 3
            j += 1
        else:  # i
            result[i] = 2
        i += 1
    return result


def fleiss_kappa(m):
    num_items = len(m)
    num_categories = len(m[0])
    num_annotators = sum(m[0])
    num_annotations = num_annotators * num_items
    observed_agreements = sum([sum([i * i for i in item]) for item in m]) - num_annotations
    observed_agreement = observed_agreements / float(num_annotators * (num_annotators - 1)) / num_items
    distribution = [sum([item[c] for item in m]) / float(num_annotations) for c in xrange(num_categories)]
    expected_agreement = sum([p * p for p in distribution])
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def calculate_agreement(files, relaxed, consider_discontinuous, entity_filter):
    annotations = map(lambda f: annotation.TextAnnotations(f), files)
    agreement = Agreement(annotations)
    agreement.filter_entity_types = entity_filter
    agreement.ignore_discontinuous = not consider_discontinuous
    if relaxed:
        agreement.strict_entity_offset = False
        agreement.strict_entity_type = False

    # print agreement.entity_span_fleiss_kappa()
    print agreement.exact_match_score()


def argparser():
    ap = argparse.ArgumentParser(description="Calculate inter-annotator agreement")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--relaxed", action="store_true")
    ap.add_argument("--considerDiscontinuous", action="store_true")
    ap.add_argument("--entityTypes", nargs="*", help="Consider only entities of listed types")
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv
    args = argparser().parse_args(argv[1:])

    files = []
    errors = []
    for path in args.paths:
        diff_and_mark.add_files(files, path, errors)
    print "{} errors encountered in reading files".format(len(errors))

    calculate_agreement(files, args.relaxed, args.considerDiscontinuous, args.entityTypes)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))