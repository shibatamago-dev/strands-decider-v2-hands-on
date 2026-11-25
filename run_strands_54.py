"""Strands Decider v2 E2B をボスの54問で動かすドライバ。

前提: Colab で `strands-decider serve StrandsAgents/strands-decider-E2B-gemma4-v2-2611`
      が localhost:8000 で起動済み。gemini-decision-1-hands-on をカレントに clone 済み。

使い方:
    python3 run_strands_54.py               # 全54問（画像が通れば）
    python3 run_strands_54.py --probe-only  # 画像1件だけ試して終わる
    python3 run_strands_54.py --text-only   # design_doc（テキスト8問）だけ実行

結果は strands_54_results.json に保存し、要約を標準出力に出す。
判定ルールはボスの standalone_run.py / analyze.py と同じ:
  noul: noul>=0.5 が got、choice: 完全一致、score: |got-exp|<=0.6
  カバレッジ: 確信度降順で誤差率5%以下に収まる最大prefixの割合
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "http://localhost:8000/v1/systemone"
OUT = Path("strands_54_results.json")

# --- 54問の読み込み（ボスのリポジトリをそのまま使う） ----------------------
for cand in ("gemini-decision-1-hands-on", "/content/gemini-decision-1-hands-on"):
    if Path(cand, "standalone_run.py").exists():
        sys.path.insert(0, cand)
        break
else:
    print("ERROR: gemini-decision-1-hands-on/standalone_run.py が見つかりません", file=sys.stderr)
    sys.exit(2)

import standalone_run as sr  # noqa: E402  (CASES を持つ)


def call_server(payload, timeout=300):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return None, (time.time() - t0) * 1000, e.code, e.read().decode("utf-8", "replace")[:500]
    return data, (time.time() - t0) * 1000, 200, ""


def confidence_of(ans):
    if ans.get("confidence") is not None:
        return float(ans["confidence"])
    t = ans.get("type")
    if t == "noul" and ans.get("noul") is not None:
        n = float(ans["noul"])
        return max(n, 1.0 - n)
    probs = ans.get("probabilities")
    if probs:
        vals = probs.values() if isinstance(probs, dict) else probs
        return float(max(vals))
    return None


def judge_one(qid, exp, ans):
    t = ans.get("type")
    if t == "noul":
        got = ans.get("noul") is not None and float(ans["noul"]) >= 0.5
        return {"expected": exp, "got": got, "noul": ans.get("noul"),
                "confidence": confidence_of(ans), "pass": got == exp}
    if t == "choice":
        got = ans.get("choice")
        return {"expected": exp, "got": got, "probabilities": ans.get("probabilities"),
                "confidence": confidence_of(ans), "pass": got == exp}
    if t == "score":
        got = ans.get("score")
        ok = got is not None and abs(float(got) - float(exp)) <= 0.6
        return {"expected": exp, "got": got, "probabilities": ans.get("probabilities"),
                "confidence": confidence_of(ans), "pass": ok}
    return {"expected": exp, "got": None, "pass": False,
            "note": f"unexpected answer type {t!r}", "confidence": None}


def build_payload(case):
    text_parts, images = [], []
    for block in case["input"]:
        if block["type"] == "text":
            text_parts.append(block["text"])
        elif block["type"] == "image":
            images.append(block["data"])
    payload = {"state": "\n".join(text_parts), "questions": case["questions"]}
    if images:
        payload["images"] = images
    return payload


def run_cases(cases):
    results, total_q, passed_q = [], 0, 0
    for case in cases:
        payload = build_payload(case)
        data, elapsed_ms, status, err = call_server(payload)
        if data is None:
            print(f"=== {case['name']} === HTTP {status}: {err}", flush=True)
            results.append({"case": case["name"], "http_status": status,
                            "error": err, "verdicts": {}})
            continue
        answers = data.get("answers", {})
        verdicts = {}
        for qid, exp in case["expected"].items():
            ans = answers.get(qid, {})
            v = judge_one(qid, exp, ans)
            verdicts[qid] = v
            total_q += 1
            passed_q += 1 if v["pass"] else 0
            mark = "OK  " if v["pass"] else "MISS"
            print(f"  [{mark}] {case['name']} :: {qid}: "
                  f"expected={v['expected']!r} got={v.get('got')!r} "
                  f"conf={v.get('confidence')}", flush=True)
        print(f"=== {case['name']} === server_latency={data.get('latency_ms')}ms "
              f"client={elapsed_ms:.0f}ms", flush=True)
        results.append({"case": case["name"], "elapsed_ms": round(elapsed_ms),
                        "server_latency_ms": data.get("latency_ms"),
                        "response": data, "verdicts": verdicts})
    return results, total_q, passed_q


def summarize(results, total_q, passed_q):
    rows = []
    for r in results:
        for qid, v in r["verdicts"].items():
            ans_type = None
            a = r["response"]["answers"].get(qid, {})
            ans_type = a.get("type")
            rows.append({"case": r["case"], "qid": qid, "type": ans_type,
                         "pass": v["pass"], "confidence": v.get("confidence"),
                         "expected": v["expected"], "got": v.get("got")})
    print(f"\nSUMMARY: {passed_q}/{total_q} questions correct "
          f"across {len(results)} cases")
    # カバレッジ（確信度のある行だけ。ボスと同じ定義）
    scored = [x for x in rows if x["confidence"] is not None]
    if scored and len(scored) == len(rows):
        srt = sorted(scored, key=lambda x: -x["confidence"])
        best, errs = 0, 0
        for i, x in enumerate(srt, 1):
            errs += 0 if x["pass"] else 1
            if errs / i <= 0.05:
                best = i
        print(f"coverage@5%error: {best}/{len(rows)} = {best/len(rows):.3f}")
        cov = best
    else:
        print(f"coverage: skipped ({len(rows)-len(scored)} rows without confidence)")
        cov = None
    for th in (0.5, 0.8, 0.9, 0.95, 0.99):
        sel = [x for x in scored if x["confidence"] >= th]
        if sel:
            e = sum(1 for x in sel if not x["pass"]) / len(sel)
            print(f"conf>={th}: n={len(sel)} ({len(sel)/len(rows):.1%}) error={e:.1%}")
    from collections import defaultdict
    by = defaultdict(lambda: [0, 0])
    for x in rows:
        by[x["case"]][1] += 1
        by[x["case"]][0] += 1 if x["pass"] else 0
    for k, (p, t) in by.items():
        print(f"{k}: {p}/{t}")
    by = defaultdict(lambda: [0, 0])
    for x in rows:
        by[x["type"]][1] += 1
        by[x["type"]][0] += 1 if x["pass"] else 0
    for k, (p, t) in by.items():
        print(f"type {k}: {p}/{t}")
    print("\nmisses:")
    for x in rows:
        if not x["pass"]:
            print(f"  {x['case']} :: {x['qid']} expected={x['expected']!r} "
                  f"got={x['got']!r} conf={x['confidence']}")
    txt = [x for x in rows if x["case"] == "design_doc"]
    if txt:
        print(f"\ntext-only (design_doc): "
              f"{sum(1 for x in txt if x['pass'])}/{len(txt)}")
    img = [x for x in rows if x["case"] != "design_doc"]
    if img:
        print(f"image questions: {sum(1 for x in img if x['pass'])}/{len(img)}")
    return {"total": total_q, "passed": passed_q,
            "coverage_at_5pct": cov, "rows": rows}


def main():
    probe_only = "--probe-only" in sys.argv
    text_only = "--text-only" in sys.argv
    cases = sr.CASES
    print(f"cases: {len(cases)}, "
          f"questions: {sum(len(c['questions']) for c in cases)}", flush=True)
    if probe_only:
        # 画像が通るかの確認だけ（道路・空き画像、4問）
        target = [c for c in cases if c["name"] == "road/road-clean.png"]
        results, total_q, passed_q = run_cases(target)
        summary = summarize(results, total_q, passed_q)
        OUT.write_text(json.dumps(
            {"summary": summary, "results": results},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if text_only:
        cases = [c for c in cases if c["name"] == "design_doc"]
    results, total_q, passed_q = run_cases(cases)
    summary = summarize(results, total_q, passed_q)
    OUT.write_text(json.dumps(
        {"summary": summary, "results": results},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFull raw results saved to {OUT}")


if __name__ == "__main__":
    main()
