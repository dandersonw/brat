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
        precisions = self.per_file_per_annotator_pair(self._entity_precision)
        precisions = reduce_by_tuple_sum([reduce_by_tuple_sum(pair) for pair in precisions])
        return float(precisions[0]) / precisions[1]

    def relation_f1(self):
        precisions = self.per_file_per_annotator_pair(self._relation_precision)
        precisions = reduce_by_tuple_sum([reduce_by_tuple_sum(pair) for pair in precisions])
        return float(precisions[0]) / precisions[1]

    def per_file_per_annotator_pair(self, score_function):
        result = []
        annotators = set((a.annotator_id for a in self.annotations))
        for combination in itertools.combinations(annotators, 2):
            scores = []
            for (doc_name, annotations) in self.annotations_grouped_by_document(combination):
                scores.append(score_function(annotations[0], annotations[1]))
                scores.append(score_function(annotations[1], annotations[0]))
            result.append(scores)
        return result

    def entity_span_fleiss_kappa(self):
        category_counts = []
        for (doc_name, annotations) in self.annotations_grouped_by_document(None):
            annotations = list(annotations)
            if len(set(len(d) for d in annotations)) != 1:
                annotations = ai2_common.docs_with_compatible_tokenization(annotations)
                assert len(set(len(d) for d in annotations)) == 1
            doc_len = len(annotations[0])
            document_counts = np.zeros((doc_len, 2)).tolist()
            for doc in annotations:
                labels = entity_or_not_per_idx(doc.entities, doc_len)
                for i in xrange(doc_len):
                    document_counts[i][labels[i]] += 1
            category_counts += document_counts
        return fleiss_kappa(category_counts)

    def entity_span_krippendorff_alpha(self):
        annotator_set = set((doc.annotator_id for doc in self.annotations))
        # Character level
        aggregated_regions = dict()
        total_len = 0
        for (doc_name, annotations) in self.annotations_grouped_by_document(None):
            # We need all annotators to have annotated each doc
            assert annotator_set == set((doc.annotator_id for doc in annotations))
            doc_len = len(annotations[0].brat_annotation.get_document_text())
            for doc in annotations:
                spans = [e.spans for e in doc.brat_annotation.get_entities()]
                regions = krippendorf_regions(spans, doc_len)
                offset_spans(regions, total_len)
                aggregated_regions[doc.annotator_id].append(regions)
            total_len += doc_len
        aggregated_regions = aggregated_regions.values()
        


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

    def annotations_grouped_by_document(self, annotators_filter):
        result = defaultdict(list)
        remove_random_prefix = re.compile(r"^[0-9]+_([0-9]+)$")
        for doc in self.annotations:
            if annotators_filter is not None and doc.annotator_id not in annotators_filter:
                continue
            name = doc.document_id
            match = remove_random_prefix.match(name)
            if match is not None:
                name = match.group(1)
            result[name].append(doc)
        return result.items()


def reduce_by_tuple_sum(tuples):
    return reduce(lambda a, b: map(lambda i, j: i + j, a, b), tuples)


# Just fills in where a span covers. Agnostic to overlapping or discontinuous spans.
def entity_or_not_per_idx(entities, total_len):
    result = [0] * total_len
    for e in entities:
        for span in e.spans:
            for i in xrange(span[0], span[1]):
                result[i] = 1
    return result


# As defined in Krippendorf 1995
def krippendorff_alpha(annotator_regions, total_len):
    B = float(len(annotator_regions))
    N = float(sum((len(regions for regions in annotator_regions))))
    L = float(total_len)
    expected_denom = B * L * (B * L - 1) * L
    expected_denom -= L * sum([
        sum((span[2]
             * (span[1] - span[0])
             * (span[1] - span[0] - 1)
             for span in region))
        for region in annotator_regions])
    expected_num = 0
    for region in annotator_regions:
        for span in region:
            l = span[1] - span[0]
            if span[2]:
                expected_num += ((N - 1) / 3) * (2 * pow(l, 3) - 3 * pow(l, 2) + l)
            # TODO: seemingly redundant other piece of piecewise function here
    expected_num *= 2
    expected_disagreement = expected_num / expected_denom

    observed_disagreement = 0
    for region_a in annotator_regions:
        for span_a in region_a:
            for region_b in annotator_regions:
                for span_b in region_b:
                    # Calculate distance
                    intersect = span_a[0] < span_b[1] and span_b[0] > span_a[1]
                    contain = (span_a[0] <= span_b[0] and span_a[1] >= span_b[0]
                               or span_b[0] <= span_a[0] and span_b[1] >= span_a[0])
                    if span_a[2] and span_b[2] and intersect:
                        left_distance = span_b[0] - span_a[0]
                        right_distance = span_b[1] - span_a[1]
                        observed_disagreement += pow(left_distance, 2) + pow(right_distance, 2)
                    if span_a[2] ^ span_b[2] and contain:
                        observed_disagreement += pow(span_a[1] - span_a[0], 2)
    observed_disagreement /= B * (B - 1) * pow(L, 2)
    return 1 - (observed_disagreement / expected_disagreement)


def krippendorf_regions(spans, total_len):
    spans = sorted(set(spans))
    regions = []
    for span in spans:
        last = regions[-1][1] if regions else 0
        if last < span[0]:
            regions.append((last, span[0], False))
        elif last > span[0]:  # Let us try and paper over overlapping spans
            if last < span[1]:
                regions.append((last, span[1], True))
            continue
        regions.append((span[0], span[1], True))
    last = regions[-1][1] if regions else 0
    if last < total_len:
        regions.append((last, total_len, False))
    return regions


def offset_spans(spans, offset):
    for span in spans:
        span[0] += offset
        span[1] += offset

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

    report_scores(agreement.entity_span_fleiss_kappa(), "Fleiss Kappa")


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
