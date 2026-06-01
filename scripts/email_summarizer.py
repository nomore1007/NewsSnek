import sys
import json

def summarize(messages):
    # Very simple heuristic: count messages and list subjects
    subs = [m.split('| Subject: ')[1].split(' |')[0] for m in messages]
    summary = f"You have {len(messages)} new emails. Topics: " + ", ".join(subs) + "."
    return summary

if __name__ == "__main__":
    lines = [line.strip() for line in sys.stdin if line.strip()]
    print(summarize(lines))
