"""
Phase E - score_hmm_calibration.py

Ground-truth ERS-mode labeling rule (DOCUMENT THIS EXPLICITLY - it's a
modeling assumption bridging continuous Simscape output to the HMM's
discrete taxonomy, not a physically derived fact):

    CONFIRMED SIGN CONVENTION (validated against Simscape ground truth):
    true_current_A < 0 = discharge (power/acceleration)
    true_current_A > 0 = charging/regen (braking)

    Lharvest : true_current_A > 0                            (net charging/regen)
    Lderate  : true_current_A <= 0 AND true_SOC < 0.10        (discharging, but suppressed by low SOC)
    H        : true_current_A <= -0.6 * DEPLOY_CEILING_A      (near-max deploy, i.e. large-magnitude discharge)
    M        : everything else discharging (not near-max, SOC not critical)

Requires:
  - rival_ground_truth_<RIVAL_ID>.csv  (from Phase A/Simscape)
        columns: time_s, true_current_A, true_SOC
        must be the SAME driver/lap/track as Phase C/D, on a compatible clock
  - rival_belief_output_<RIVAL_ID>.csv (from Phase D)

Before trusting any number this script prints:
  1. Confirm gap_s in Phase C was a REAL trace, not the placeholder constant.
  2. Sanity-check the true_ers distribution below isn't degenerate (e.g. ~95%
     one label) before drawing conclusions - that usually means a sign
     convention or threshold in the labeling rule is off, not that the HMM
     is bad.
"""
import pandas as pd
from pathlib import Path
RIVAL_ID = 'HAM'
DEPLOY_CEILING_A = 437.5  # from your own script's mguk_max / V_PACK_ASSUMED - confirm this value
SOC_FLOOR = 0.10
truth = pd.read_csv(
    Path(__file__).parent / f'rival_ground_truth_{RIVAL_ID}.csv'
)

belief = pd.read_csv(
    Path(__file__).parent / f'rival_belief_output_{RIVAL_ID}.csv'
)

merged = pd.merge_asof(
    belief.sort_values('time_s'),
    truth.sort_values('time_s'),
    on='time_s',
)


def true_label(row):
    if row['true_current_A'] > 0:
        return 'Lharvest'
    if row['true_SOC'] < SOC_FLOOR:
        return 'Lderate'
    if row['true_current_A'] <= -0.6 * DEPLOY_CEILING_A:
        return 'H'
    return 'M'


merged['true_ers'] = merged.apply(true_label, axis=1)

print("true_ers label distribution (sanity-check this first):")
print(merged['true_ers'].value_counts(normalize=True))
print()

# Accuracy (point estimate, argmax vs label)
accuracy = (merged['most_likely_ers'] == merged['true_ers']).mean()

# Calibration (Brier score) - rewards a well-calibrated full distribution,
# not just whether the argmax happened to be right.
def brier(r):
    correct = (1 - r[f"ers_{r['true_ers']}"]) ** 2
    incorrect = sum(
        r[f"ers_{m}"] ** 2 for m in ['H', 'M', 'Lharvest', 'Lderate'] if m != r['true_ers']
    )
    return correct + incorrect


merged['brier'] = merged.apply(brier, axis=1)

print(f"Accuracy: {accuracy:.3f}")
print(f"Mean Brier score: {merged['brier'].mean():.3f}  (0 = perfect, 2 = worst)")
print()
print("Confusion matrix (rows = true, cols = predicted):")
print(pd.crosstab(merged['true_ers'], merged['most_likely_ers']))

merged.to_csv(f'rival_scored_{RIVAL_ID}.csv', index=False)
print(f"\nSaved per-tick scored output to rival_scored_{RIVAL_ID}.csv")