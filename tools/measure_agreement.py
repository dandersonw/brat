#!/usr/bin/env python
# 0-*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-

from __future__ import with_statement
from scipy import stats
from sys import path as sys_path
from collections import defaultdict
import ai2_common
import numpy as np
import argparse
import itertools
import os.path
import re

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

    def entity_f1(self):
        precisions = self.per_file_scores(self._entity_precision)
        precisions = reduce(lambda a, b: map(lambda i, j: i + j, a, b), precisions)
        return float(precisions[0]) / precisions[1]

    def relation_f1(self):
        precisions = self.per_file_scores(self._relation_precision)
        precisions = reduce(lambda a, b: map(lambda i, j: i + j, a, b), precisions)
        return float(precisions[0]) / precisions[1]

    def per_file_scores(self, score_function):
        scores = []
        for (doc_name, annotations) in self.annotations_grouped_by_document():
            for combination in itertools.combinations(annotations, 2):
                scores.append(score_function(combination[0], combination[1]))
                scores.append(score_function(combination[1], combination[0]))
        return scores

    def _entity_span_fleiss_kappa(self):
        spans = map(lambda e: self._get_entity_spans(e), self.annotations)
        total_len = len(self.annotations[0].get_document_text())
        biluo = map(lambda s: spans_to_biluo(s, total_len), spans)
        category_counts = np.zeros((total_len, 5))
        for annotator in biluo:
            for i in xrange(total_len):
                category_counts[i][annotator[i]] += 1
        return fleiss_kappa(category_counts)

    def _get_entity_spans(self, doc):
        return list(itertools.chain.from_iterable(
            [e.spans for e in doc.entities if self._entity_is_included(e)]))

    def _entity_f1(self, gold, notGold):
        precision = self._entity_precision(gold, notGold)
        recall = self._entity_precision(notGold, gold)
        if 0 in precision + recall:
            return 0
        recall = float(recall[0]) / recall[1]
        precision = float(precision[0]) / precision[1]
        return stats.hmean([precision, recall])

    def _relation_f1(self, gold, notGold):
        precision = self._relation_precision(gold, notGold)
        recall = self._relation_precision(notGold, gold)
        if 0 in precision + recall:
            return 0
        precision = float(precision[0]) / precision[1]
        recall = float(recall[0]) / recall[1]
        return stats.hmean([precision, recall])

    def _entity_precision(self, gold, notGold):
        entities = [e for e in notGold.entities if self._entity_is_included(e)]
        found = [e for e in entities if self._find_matching_entities(gold, e)]
        return (len(found), len(entities))

    def _relation_precision(self, gold, not_gold):
        relations = list(self._filter_relations(not_gold.relations))
        if self.restricted_relation_scoring:
            relations = [r for r in relations if self._entity_matches_exist(gold, r)]

        found = [r for r in relations if self._find_matching_relations(gold, r)]
        return (len(found), len(relations))

    def _entity_matches_exist(self, gold, relation):
        return (self._find_matching_entities(gold, relation.arg1)
                and self._find_matching_entities(gold, relation.arg2))

    def _find_matching_entities(self, gold, entity):
        return [e for e in gold.entities if self._entities_match(e, entity)]

    def _find_matching_relations(self, gold, relation):
        return [r for r in gold.relations if self._relations_match(r, relation)]

    def _entity_is_included(self, e):
        return ((self.filter_entity_types is None or e.type in self.filter_entity_types)
                and (self.ignore_discontinuous is False or len(e.spans) == 1))

    def _filter_relations(self, relations):
        if self.filter_relation_types is None:
            return relations
        else:
            return filter(lambda r: r.type in self.filter_relation_types, relations)

    def _entities_match(self, a, b):
        return (not self.strict_entity_type or a.type == b.type) \
            and (not self.strict_entity_offset and a.overlaps(b) or a.same_span(b))

    def _relations_match(self, a, b):
        return (self._entities_match(a.arg1, b.arg1)
                and self._entities_match(a.arg2, b.arg2)
                and (not self.strict_relation_type or a.type == b.type))

    def annotations_grouped_by_document(self):
        result = defaultdict(list)
        remove_random_prefix = re.compile(r"^[0-9]+_([0-9]+)$")
        for doc in self.annotations:
            name = os.path.basename(doc.brat_annotation.get_document())
            match = remove_random_prefix.match(name)
            if match is not None:
                name = match.group(1)
            result[name].append(doc)
        return result.items()


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


def calculate_agreement(docs, relaxed, consider_discontinuous, filter_entity_types, filter_relation_types):
    agreement = Agreement(docs)
    agreement.filter_entity_types = filter_entity_types
    agreement.filter_relation_types = filter_relation_types
    agreement.ignore_discontinuous = not consider_discontinuous
    # modes for entity scores
    if relaxed:
        agreement.strict_entity_offset = False
        agreement.strict_entity_type = False
    else:
        agreement.strict_entity_offset = True
        agreement.strict_entity_type = True

    # print agreement.entity_span_fleiss_kappa()
    report_scores(agreement.entity_f1(), "Entity F1")
    # modes for relation scores
    agreement.strict_entity_offset = True
    agreement.strict_entity_type = False
    if relaxed:
        agreement.strict_relation_type = False
        agreement.restricted_relation_scoring = True
    else:
        agreement.strict_relation_type = True
        agreement.restricted_relation_scoring = False

    report_scores(agreement.relation_f1(), "Relation F1")


def report_scores(scores, name):
    print "-" * 60
    print name
    print scores


def argparser():
    ap = argparse.ArgumentParser(description="Calculate inter-annotator agreement")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--relaxed", action="store_true")
    ap.add_argument("--considerDiscontinuous", action="store_true")
    ap.add_argument("--entityTypes", nargs="*", help="Consider only entities of listed types")
    ap.add_argument("--relationTypes", nargs="*", help="Consider only relations of listed types")
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv
    args = argparser().parse_args(argv[1:])

    docs = ai2_common.get_docs(*args.paths)

    calculate_agreement(docs,
                        args.relaxed,
                        args.considerDiscontinuous,
                        args.entityTypes,
                        args.relationTypes)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
