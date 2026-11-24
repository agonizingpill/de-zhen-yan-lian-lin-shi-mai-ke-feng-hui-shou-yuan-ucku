import json

from fastapi import HTTPException
from sqlalchemy import select

from core.db import transaction
from domain.interventions import findings, tickets
from domain.soundboard import points, windows


def one(conn,table,code,lock=False):
    query=select(table).where(table.c.code==code)
    row=conn.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise HTTPException(404,f"没有编号为 {code} 的记录")
    return dict(row)


def query(conn,table,*filters):
    stmt=select(table).where(*filters).order_by(table.c.code.desc()).limit(160)
    return [dict(row) for row in conn.execute(stmt).mappings()]


def calibration(conn):
    # 新诊断与备用路复测共用这一基线入口；撤回样本在此被排除。
    return query(conn,windows,windows.c.purpose=="baseline",windows.c.withdrawn == False)  # noqa: E712


def same_slot(conn,focus):
    return query(conn,windows,windows.c.slot==focus["slot"],windows.c.purpose=="live")


def latest(conn,point,purpose):
    stmt=select(windows).where(windows.c.point==point["code"],windows.c.revision==point["revision"],
                               windows.c.purpose==purpose).order_by(windows.c.slot.desc()).limit(1)
    row=conn.execute(stmt).mappings().first()
    return dict(row) if row else None


def withdrawn_codes(conn):
    rows=conn.execute(select(windows.c.code).where(windows.c.withdrawn == True)).all()  # noqa: E712
    return {row[0] for row in rows}


def present_window(row):
    data=dict(row)
    withdrawn=bool(data.get("withdrawn"))
    data["withdrawn"]=withdrawn
    data["is_withdrawn"]=withdrawn
    data["revoked"]=withdrawn
    data["state"]="withdrawn" if withdrawn else "active"
    data["status"]=data["state"]
    return data


def _codes_from(value):
    if value is None:
        return []
    if isinstance(value,str):
        try:
            value=json.loads(value)
        except (ValueError,TypeError):
            return [value]
    if isinstance(value,dict):
        for key in ("codes","windows","samples","items"):
            if key in value:
                return _codes_from(value[key])
        return []
    if isinstance(value,(list,tuple,set)):
        codes=[]
        for item in value:
            if isinstance(item,str) and item:
                codes.append(item)
            elif isinstance(item,dict) and item.get("code"):
                codes.append(str(item["code"]))
        return codes
    return []


def basis_codes(raw):
    if raw is None:
        return None
    codes=_codes_from(raw)
    return codes


def present_finding(row,withdrawn=None):
    data=dict(row)
    withdrawn=withdrawn if withdrawn is not None else set()
    raw_basis=data.get("basis",None)
    # 旧记录没有 basis 列值：无法还原用样依据，标记为无法核实。
    codes=basis_codes(raw_basis) if raw_basis is not None else None
    verifiable=codes is not None
    detail=data.get("basis_detail")
    if isinstance(detail,str):
        try:
            detail=json.loads(detail)
        except (ValueError,TypeError):
            detail=None
    if not isinstance(detail,dict):
        detail=None
    used=set(codes or [])
    simultaneous=_codes_from(detail.get("simultaneous")) if detail else []
    used.update(simultaneous)
    if detail and isinstance(detail.get("focus"),str):
        used.add(detail["focus"])
    refs=sorted(code for code in used if code in withdrawn)
    data.update({
        "basis": codes,
        "basis_codes": codes,
        "sample_basis": codes,
        "sample_refs": codes,
        "reference_codes": codes,
        "references": codes,
        "used_samples": sorted(used) if verifiable else None,
        "simultaneous_codes": simultaneous,
        "basis_count": len(codes or []),
        "verifiable": verifiable,
        "unverifiable": not verifiable,
        "verification": "verified" if verifiable else "unverifiable",
        "verify_status": "verified" if verifiable else "unverifiable",
        "basis_status": "recorded" if verifiable else "missing",
        "withdrawn_refs": refs,
        "withdrawn_samples": refs,
        "withdrawn_codes": refs,
        "uses_withdrawn_sample": bool(refs),
        "uses_withdrawn": bool(refs),
        "has_withdrawn": bool(refs),
        "affected": bool(refs),
        "impacted": bool(refs),
        "basis_detail": detail,
        "basis_snapshot": detail,
    })
    return data


def impact_in_conn(conn,code):
    sample=present_window(one(conn,windows,code))
    withdrawn=withdrawn_codes(conn)
    items=[present_finding(row,withdrawn) for row in query(conn,findings)]
    affected=[item for item in items if code in (item.get("used_samples") or [])]
    unverifiable=[item for item in items if not item["verifiable"]]
    codes=[item["code"] for item in affected]
    return {
        "sample": sample, "code": code, "sample_code": code,
        "withdrawn": sample["withdrawn"],
        "findings": affected, "affected_findings": affected,
        "affected": codes, "affected_codes": codes, "count": len(affected),
        "unverifiable_findings": unverifiable, "unverifiable_count": len(unverifiable),
    }


def verification_in_conn(conn,code):
    row=one(conn,findings,code)
    data=present_finding(row,withdrawn_codes(conn))
    used=data.get("used_samples") or []
    samples=[]
    if used:
        rows=conn.execute(select(windows).where(windows.c.code.in_(used))).mappings().all()
        by_code={item["code"]: present_window(dict(item)) for item in rows}
        for sample_code in used:
            samples.append(by_code.get(sample_code,{"code":sample_code,"missing":True,"withdrawn":False}))
    data["samples"]=samples
    data["basis_samples"]=samples
    data["original_score"]=data.get("score")
    if data["verifiable"]:
        data["reason"]=None
        data["message"]="用样依据已随结论签存，计算凭证过期后仍可核对原分数与样本。"
    else:
        data["reason"]="missing_basis"
        data["message"]="旧记录缺少用样依据，无法核实该结论当时使用的样本。"
    return data


def patchboard():
    with transaction() as conn:
        return {"points":query(conn,points),"tickets":query(conn,tickets)}


def audio():
    with transaction() as conn:
        return [present_window(row)
                for row in query(conn,windows,windows.c.purpose!="baseline")]


def baseline_view():
    with transaction() as conn:
        return [present_window(row)
                for row in query(conn,windows,windows.c.purpose=="baseline")]


def withdrawals_view():
    with transaction() as conn:
        return [present_window(row)
                for row in query(conn,windows,windows.c.withdrawn == True)]  # noqa: E712


def samples_view(purpose=None):
    with transaction() as conn:
        if purpose in (None,"all",""):
            rows=query(conn,windows)
        elif purpose=="baseline":
            rows=query(conn,windows,windows.c.purpose=="baseline")
        else:
            rows=query(conn,windows,windows.c.purpose==purpose)
        return [present_window(row) for row in rows]


def sample_view(code):
    with transaction() as conn:
        return present_window(one(conn,windows,code))


def impact_view(code):
    with transaction() as conn:
        return impact_in_conn(conn,code)


def diagnosis():
    with transaction() as conn:
        withdrawn=withdrawn_codes(conn)
        return [present_finding(row,withdrawn) for row in query(conn,findings)]
