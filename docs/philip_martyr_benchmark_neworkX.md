# Overall Aggregated Variant Graph Summary with dekker (default) collatex algorithm

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

#We compare the node count between each ref for each strategy. A enriched strategy ref has an average of 105 nodes.


##EXTRA summaries with different collatex algorithms:

# Overall Aggregated Variant Graph Summary with Needleman_wunsch collatex algorithm

======================================================================
### OVERALL AGGREGATED VARIANT GRAPH SUMMARY (ALL REFERENCES)
======================================================================
| Strategy/Parameter        | Tokens   | Nodes (V)  | Edges (E)  | Merge Ratio  | Var Points  | Time     |
|---------------------------|----------|------------|------------|--------------|-------------|----------|
| Enriched (lemma+pos)      | 13212    | 4482       | 6224       | 2.948        | 1574        | 19.47  s |
| Enriched (lemma)          | 13212    | 4280       | 5949       | 3.087        | 1521        | 17.43  s |
| Enriched (text)           | 13212    | 4573       | 6334       | 2.889        | 1591        | 17.70  s |
| Raw (text)                | 13879    | 4979       | 6902       | 2.788        | 1665        | 2.02   s |


# Overall Aggregated Variant Graph Summary with Medite collatex algorithm

======================================================================
### OVERALL AGGREGATED VARIANT GRAPH SUMMARY (ALL REFERENCES)
======================================================================
| Strategy/Parameter        | Tokens   | Nodes (V)  | Edges (E)  | Merge Ratio  | Var Points  | Time     |
|---------------------------|----------|------------|------------|--------------|-------------|----------|
| Enriched (lemma+pos)      | 13212    | 5516       | 8006       | 2.395        | 2234        | 28.54  s |
| Enriched (lemma)          | 13212    | 5184       | 7514       | 2.549        | 2088        | 27.70  s |
| Enriched (text)           | 13212    | 5359       | 7592       | 2.465        | 1990        | 26.23  s |
| Raw (text)                | 13879    | 6057       | 8533       | 2.291        | 2157        | 5.11   s |
