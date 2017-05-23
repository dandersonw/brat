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
        # Entities/relations only match if they have the same type
        self.strict_entity_type = True
        self.strict_relation_type = True
        # A set of entity types to consider for scoring (or None to consider all)
        self.filter_entity_types = None
        self.filter_relation_types = None
        # Require perfect span match to consider entities matching, or allow any span overlap
        self.strict_entity_offset = True
        # Ignore entities that are not annotated as one continuous mention
        self.ignore_discontinuous = True
        # Only count, for the purposes of scoring relation f1, relations for
        # which a relation with matching entities can be found in the other
        # document
        self.restricted_relation_scoring = False

    def pairwise_scores(self, score_function):
        scores = []
        for (doc_name, annotations) in self.annotations_grouped_by_document():
            for combination in itertools.combinations(annotations, 2):
                scores.append(score_function(combination[0], combination[1]))
                scores.append(score_function(combination[1], combination[0]))
        return scores

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

    def entity_f1(self, gold, notGold):
        precision = self.entity_precision(gold, notGold)
        recall = self.entity_recall(gold, notGold)
        if precision == 0 or recall == 0:
            return 0
        return stats.hmean([precision, recall])

    def relation_f1(self, gold, notGold):
        precision = self.relation_precision(gold, notGold)
        recall = self.relation_recall(gold, notGold)
        if precision == 0 or recall == 0:
            return 0
        return stats.hmean([precision, recall])

    def entity_precision(self, gold, notGold):
        entities = [e for e in notGold.get_entities() if self.entity_is_included(e)]
        if len(entities) == 0:
            return 1
        found = [e for e in entities if self.find_matching_entities(gold, e)]
        return float(len(found)) / len(entities)

    def entity_recall(self, gold, not_gold):
        return self.entity_precision(not_gold, gold)

    def relation_precision(self, gold, not_gold):
        relations = list(self.filter_relations(not_gold.get_relations()))
        gold_id_entity = self.entity_id_map(gold)
        not_gold_id_entity = self.entity_id_map(not_gold)
        if self.restricted_relation_scoring:
            relations = [r for r in relations if
                         self.entity_matches_exist(gold, r, not_gold_id_entity)]

        if len(relations) == 0:
            return 1
        found = [r for r in relations if
                 self.find_matching_relations(gold, r, gold_id_entity, not_gold_id_entity)]
        return float(len(found)) / len(relations)

    def relation_recall(self, gold, notGold):
        return self.entity_recall(notGold, gold)

    def entity_matches_exist(self, gold, relation, id_entity_map):
        return (self.find_matching_entities(gold, id_entity_map[relation.arg1])
                and self.find_matching_entities(gold, id_entity_map[relation.arg2]))

    def find_matching_entities(self, gold, entity):
        return [e for e in gold.get_entities() if self.entities_match(e, entity)]

    def find_matching_relations(self, gold, relation, gold_id_entity, not_gold_id_entity):
        return [r for r in gold.get_relations() if
                self.relations_match(r, relation, gold_id_entity, not_gold_id_entity)]

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
            and ((not self.strict_entity_offset and any_overlapping_spans(a, b))
                 or a.same_span(b))

    def relations_match(self, a, b, a_id_entity, b_id_entity):
        return (self.entities_match(a_id_entity[a.arg1], b_id_entity[b.arg1])
                and self.entities_match(a_id_entity[a.arg2], b_id_entity[b.arg2])
                and (not self.strict_relation_type or a.type == b.type))

    def annotations_grouped_by_document(self):
        result = defaultdict(list)
        for doc in self.annotations:
            result[os.path.basename(doc.get_document())].append(doc)
        return result.items()

    def entity_id_map(self, text_annotation):
        return {e.id: e for e in text_annotation.get_entities()}


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


def any_overlapping_spans(a, b):
        for i in a.spans:
            for j in b.spans:
                if j[0] < i[1] and i[0] < j[1]:
                    return True
        return False


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
    # modes for entity scores
    if relaxed:
        agreement.strict_entity_offset = False
        agreement.strict_entity_type = False
    else:
        agreement.strict_entity_offset = True
        agreement.strict_entity_type = True

    # print agreement.entity_span_fleiss_kappa()
    report_scores(agreement.pairwise_scores(agreement.entity_f1), "Entity F1")
    # modes for relation scores
    agreement.strict_entity_offset = False
    agreement.strict_entity_type = False
    if relaxed:
        agreement.restricted_relation_scoring = True
    else:
        agreement.restricted_relation_scoring = False

    report_scores(agreement.pairwise_scores(agreement.relation_f1), "Relation F1")


def report_scores(scores, name):
    print "-" * 60
    print name
    print stats.describe(scores)
    print scores


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
