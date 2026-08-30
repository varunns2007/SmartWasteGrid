import os
import sys
import json
import glob

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BEFORE_JSON = os.path.join(PROJECT_ROOT, "reports", "dataset_before_balance.json")
AFTER_JSON = os.path.join(PROJECT_ROOT, "reports", "dataset_after_balance.json")

def analyze():
    print("============================================================", flush=True)
    print("DATASET CLASS DISTRIBUTION ANALYSIS", flush=True)
    print("============================================================", flush=True)
    
    if os.path.exists(BEFORE_JSON):
        with open(BEFORE_JSON, "r", encoding="utf-8") as f:
            b = json.load(f)
        tot_b = b.get("0_wet", 0) + b.get("1_dry", 0) + b.get("2_recyclable", 0)
        w_pct = (b.get("0_wet", 0)/tot_b*100) if tot_b else 0
        d_pct = (b.get("1_dry", 0)/tot_b*100) if tot_b else 0
        r_pct = (b.get("2_recyclable", 0)/tot_b*100) if tot_b else 0
        
        print("BEFORE BALANCE:", flush=True)
        print(f"  Total Images:      {b.get('images')}", flush=True)
        print(f"  Wet Annotations:   {b.get('0_wet')} ({w_pct:.2f}%)", flush=True)
        print(f"  Dry Annotations:   {b.get('1_dry')} ({d_pct:.2f}%)", flush=True)
        print(f"  Recyclable Annos:  {b.get('2_recyclable')} ({r_pct:.2f}%)", flush=True)

    if os.path.exists(AFTER_JSON):
        with open(AFTER_JSON, "r", encoding="utf-8") as f:
            a = json.load(f)
        tot_a = a.get("0_wet", 0) + a.get("1_dry", 0) + a.get("2_recyclable", 0)
        w_pct_a = (a.get("0_wet", 0)/tot_a*100) if tot_a else 0
        d_pct_a = (a.get("1_dry", 0)/tot_a*100) if tot_a else 0
        r_pct_a = (a.get("2_recyclable", 0)/tot_a*100) if tot_a else 0
        
        print("\nAFTER BALANCE (FINE-TUNING DATASET):", flush=True)
        print(f"  Total Images:      {a.get('images')}", flush=True)
        print(f"  Wet Annotations:   {a.get('0_wet')} ({w_pct_a:.2f}%)", flush=True)
        print(f"  Dry Annotations:   {a.get('1_dry')} ({d_pct_a:.2f}%)", flush=True)
        print(f"  Recyclable Annos:  {a.get('2_recyclable')} ({r_pct_a:.2f}%)", flush=True)

if __name__ == "__main__":
    analyze()
