# Overall Aggregated Variant Graph Summary

======================================================================
### OVERALL AGGREGATED VARIANT GRAPH SUMMARY (ALL REFERENCES)
======================================================================
| Strategy/Parameter        | Tokens   | Nodes (V)  | Edges (E)  | Merge Ratio  | Variation Points  | Time     |
|---------------------------|----------|------------|------------|--------------|-------------------|----------|
| Enriched (lemma+pos)      | 13212    | 4470       | 6267       | 2.956        | 1623              | 17.46  s |
| Enriched (lemma)          | 13212    | 4246       | 5958       | 3.112        | 1552              | 16.08  s |
| Enriched (text)           | 13212    | 4640       | 6466       | 2.847        | 1646              | 15.69  s |
| Raw (text)                | 13879    | 5030       | 7003       | 2.759        | 1710              | 1.40   s |

#Merge Ratio = Token total / Node Total
#Variation Points = Node total that posess more than one Edge
#A node is **A unique normalized display text (`t`) value within a single column.**
#or also **a group of tokens in the same column that share the exact same display spelling (`t`).**


================================================================================
GLOBAL STATISTICAL SIGNIFICANCE (FRIEDMAN TEST)
================================================================================
Friedman chi-square statistic: 17.9255
P-value:                      1.2810e-04
Significant (alpha=0.05):     YES
================================================================================

================================================================================
PAIRWISE POST-HOC COMPARISONS (WILCOXON SIGNED-RANK TEST WITH HOLM CORRECTION)
================================================================================
| Comparison (A vs B)                        | Mean Diff (A - B) | Raw p-value  | Holm-adj p-value | Significant? |
|--------------------------------------------|-------------------|--------------|------------------|--------------|
| Enriched (lemma+pos) vs Enriched (lemma)   | +5.33             | 7.3796e-05   | 2.2139e-04       | YES          |
| Enriched (lemma+pos) vs Enriched (text)    | -4.05             | 9.7454e-03   | 9.7454e-03       | YES          |
| Enriched (lemma) vs Enriched (text)        | -9.38             | 2.1094e-04   | 4.2187e-04       | YES          |
================================================================================