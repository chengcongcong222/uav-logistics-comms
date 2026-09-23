#!/usr/bin/env python3
"""Recover OMML math and surrounding text from the problem DOCX."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
DOCX = ROOT / "data/raw/山区洪涝灾害下无人机运输与通信协同优化.docx"
OUT = ROOT / "results/e1/problem_math_extract.txt"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def omml_to_text(el: ET.Element) -> str:
    """Rough linearization of OMML."""
    tag = el.tag.split("}")[-1]
    if tag == "t":
        return el.text or ""
    if tag == "f":  # fraction
        num = el.find("m:num", NS)
        den = el.find("m:den", NS)
        n = "".join(omml_to_text(c) for c in list(num)) if num is not None else ""
        d = "".join(omml_to_text(c) for c in list(den)) if den is not None else ""
        return f"({n})/({d})"
    if tag == "sSub":
        e = el.find("m:e", NS)
        sub = el.find("m:sub", NS)
        base = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        s = "".join(omml_to_text(c) for c in list(sub)) if sub is not None else ""
        return f"{base}_{s}"
    if tag == "sSup":
        e = el.find("m:e", NS)
        sup = el.find("m:sup", NS)
        base = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        s = "".join(omml_to_text(c) for c in list(sup)) if sup is not None else ""
        return f"{base}^{s}"
    if tag == "sSubSup":
        e = el.find("m:e", NS)
        sub = el.find("m:sub", NS)
        sup = el.find("m:sup", NS)
        base = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        sb = "".join(omml_to_text(c) for c in list(sub)) if sub is not None else ""
        sp = "".join(omml_to_text(c) for c in list(sup)) if sup is not None else ""
        return f"{base}_{sb}^{sp}"
    if tag == "rad":
        deg = el.find("m:deg", NS)
        e = el.find("m:e", NS)
        body = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        d = "".join(omml_to_text(c) for c in list(deg)) if deg is not None else ""
        return f"root[{d}]({body})"
    if tag == "d":  # delimiter
        parts = ["".join(omml_to_text(c) for c in list(e)) for e in el.findall("m:e", NS)]
        return "(" + ",".join(parts) + ")"
    if tag == "nary":
        # sum/prod/int
        sub = el.find("m:sub", NS)
        sup = el.find("m:sup", NS)
        e = el.find("m:e", NS)
        ch = el.find("m:naryPr/m:chr", NS)
        op = ch.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val", "∑") if ch is not None else "∑"
        s = "".join(omml_to_text(c) for c in list(sub)) if sub is not None else ""
        p = "".join(omml_to_text(c) for c in list(sup)) if sup is not None else ""
        body = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        return f"{op}_{{{s}}}^{{{p}}}{body}"
    if tag == "func":
        fname = el.find("m:fName", NS)
        e = el.find("m:e", NS)
        fn = "".join(omml_to_text(c) for c in list(fname)) if fname is not None else ""
        body = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        return f"{fn}({body})"
    if tag == "bar":
        e = el.find("m:e", NS)
        body = "".join(omml_to_text(c) for c in list(e)) if e is not None else ""
        return f"bar({body})"
    # generic recurse
    return "".join(omml_to_text(c) for c in list(el))


def main() -> None:
    with zipfile.ZipFile(DOCX) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    lines = []
    for i, p in enumerate(root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")):
        texts = []
        for node in p.iter():
            tag = node.tag.split("}")[-1]
            if tag == "t" and node.text:
                # skip math t handled separately
                parent_is_math = any(a.tag.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/math}") for a in [])
                texts.append(node.text)
        # better: walk direct structure
        buf = []
        for child in p.iter():
            tag = child.tag.split("}")[-1]
            ns = child.tag.split("}")[0] + "}"
            if ns.endswith("wordprocessingml/2006/main}") and tag == "t":
                buf.append(child.text or "")
            elif ns.endswith("officeDocument/2006/math}") and tag == "oMath":
                buf.append(" [[MATH:" + omml_to_text(child) + "]] ")
            elif ns.endswith("officeDocument/2006/math}") and tag == "oMathPara":
                pass
        line = "".join(buf).strip()
        if line:
            lines.append(f"P{i}: {line}")

    # also extract bare oMath blocks in order with nearby text
    math_blocks = []
    for i, om in enumerate(root.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath")):
        math_blocks.append(f"M{i}: {omml_to_text(om)}")

    OUT.write_text("\n".join(lines + ["\n==== MATH BLOCKS ====" ] + math_blocks), encoding="utf-8")
    print(f"wrote {OUT}")
    print("---- paragraphs with MATH ----")
    for ln in lines:
        if "MATH" in ln or "等效" in ln or "能耗" in ln or "飞行时间" in ln or "充电" in ln or "返航" in ln or "SOC" in ln:
            print(ln)
    print("---- all math blocks ----")
    for m in math_blocks:
        print(m)


if __name__ == "__main__":
    main()
