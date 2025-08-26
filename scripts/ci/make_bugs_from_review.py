import argparse, json, pathlib, re, sys

def slug(s):
    return re.sub(r'[^a-zA-Z0-9_.-]+', '-', s.strip())[:80]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True, help="Commit SHA to read review from docs/reviews_json/<sha>.json")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parents[2]
    review_json = root / "docs" / "reviews_json" / f"{args.sha}.json"
    if not review_json.exists():
        print(f"ERROR: Missing {review_json}")
        sys.exit(1)

    data = json.loads(review_json.read_text(encoding="utf-8"))
    issues = data.get("issues", [])
    if not issues:
        print("No issues found in review JSON.")
        return 0

    out_dir = root / "bugs" / args.sha
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for it in issues:
        iid = it.get("id") or f"CR-{count+1:03d}"
        sev = (it.get("severity") or "low").lower()
        title = it.get("title") or "Untitled"
        files = it.get("files") or []
        reqs  = it.get("requirements") or []
        details = it.get("details") or ""
        go = data.get("go_no_go","GO")

        fname = f"{iid}_{slug(title)}.md"
        path = out_dir / fname

        md = []
        md.append(f"# {iid}: {title}")
        md.append("")
        md.append(f"- **Severity:** {sev}")
        md.append(f"- **Status:** open")
        md.append(f"- **Reviewed SHA:** `{args.sha}`")
        md.append(f"- **Review go/no-go:** {go}")
        if reqs:
            md.append(f"- **Requirements:** {', '.join(reqs)}")
        if files:
            md.append(f"- **Files:** {', '.join(files)}")
        md.append("")
        md.append("## Details")
        md.append(details.strip())
        md.append("")
        md.append("## Resolution Checklist")
        md.append("- [ ] Root cause understood")
        md.append("- [ ] Unit tests added/updated")
        md.append("- [ ] Integration tests added/updated")
        md.append("- [ ] Security/perf concerns addressed")
        md.append("- [ ] Docs updated (README / API_TESTING / LAUNCH_GUIDE)")
        md.append("- [ ] Linked requirements validated")
        md.append("- [ ] Verified locally")
        md.append("")
        md.append("## Fix Notes (fill during implementation)")
        md.append("- Approach:")
        md.append("- Affected modules:")
        md.append("- Follow-ups:")
        md.append("")
        path.write_text("\n".join(md), encoding="utf-8")
        count += 1

    print(f"Created/updated {count} bug files in {out_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
