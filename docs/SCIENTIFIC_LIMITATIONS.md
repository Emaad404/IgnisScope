# Scientific limitations

1. Heuristic ranking. Coverage C = sum(w*a)/sum(w); relevance R = sum(w*m*a)/sum(w*a). Weights are chosen by the
   developers (see `/api/methodology`). Not validated against expert judgement.
2. Evidence classes DIRECT, ANALOGOUS, LIMITED, UNKNOWN are application-defined, not NASA classifications.
   DIRECT is possible only for non-synthetic data with source-supported explicit microgravity context,
   comparable required measurements, sufficient coverage, and a user-attested NASA page check. The
   application does not independently verify that attestation. Terrestrial/1g evidence cannot be DIRECT.
3. Column recognition uses header names only (e.g. "pressure", "oxygen"). A wrong header gives a wrong mapping.
4. Only one phenomenon (flame spread) and exact-unit comparison are supported.
5. "Not found in the indexed corpus" means not in the files imported here.
6. Mission environments are labels. Selecting ISS, lunar or Mars fills no physical values.
7. No causal claims. controlled_counterfactual = false in every report.
8. Malformed rows are stored but excluded from scoring.
9. No DOIs are generated. Add them only after checking them yourself.
10. Sentinel values -999, -9999, and -99999 are retained only in raw cells and masked from analysis.
    They are candidates, not a universal missing-value standard; other dataset-specific sentinel codes
    require explicit review.
11. A DIRECT result is an application-defined label and does not independently establish that the
    uploaded file or its claimed source is authentic.
