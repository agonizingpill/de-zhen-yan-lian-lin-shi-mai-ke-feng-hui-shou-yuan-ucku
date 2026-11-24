from datetime import datetime, timezone

from fastapi import HTTPException

from core.audit import record
from core.db import transaction
from core.queueing import broker, result, submit
from domain.catalog import (calibration, one, present_finding, same_slot,
                            verification_in_conn, withdrawn_codes)
from domain.interventions import findings
from domain.soundboard import points, windows
from domain.states import FEATURES, Patch


def sound_snapshot(conn,focus):
    return {"focus":focus,"baseline":calibration(conn),"simultaneous":same_slot(conn,focus)}


def diagnose(form,user):
    with transaction() as conn:
        focus=one(conn,windows,form.window)
        point=one(conn,points,focus["point"])
        if focus["purpose"]!="live" or point["patch"]!=Patch.LIVE:
            raise HTTPException(409,"仅在播窗口用于判别；隔离后的试音须到复线页")
        return submit(user,{"kind":"diagnosis",**sound_snapshot(conn,focus)})


def _basis_manifest(captured,rating):
    baseline=captured.get("baseline") or []
    simultaneous=captured.get("simultaneous") or []
    focus=captured.get("focus") or {}
    codes=[row["code"] for row in baseline if isinstance(row,dict) and row.get("code")]
    manifest={
        "version":1,
        "sampled_at":datetime.now(timezone.utc).isoformat(),
        "algorithm":rating.get("algorithm"),
        "reference_windows":rating.get("reference_windows",len(baseline)),
        "threshold":rating.get("threshold"),
        "focus":focus.get("code") if isinstance(focus,dict) else None,
        "baseline":codes,
        "simultaneous":[row.get("code") for row in simultaneous
                        if isinstance(row,dict) and row.get("code")],
        "samples":[
            {"code":row.get("code"),
             **{field:row.get(field) for field in FEATURES}}
            for row in baseline if isinstance(row,dict) and row.get("code")
        ],
    }
    return codes,manifest


def save(form,user):
    computation=result(user,form.token)
    captured=computation["input"]
    rating=computation["result"]
    if captured["kind"]!="diagnosis":
        raise HTTPException(409,"请使用原始诊断凭证签入发现")
    focus=captured["focus"]
    codes,manifest=_basis_manifest(captured,rating)
    with transaction() as conn:
        point=one(conn,points,focus["point"],lock=True)
        if point["patch"]!=Patch.LIVE or point["revision"]!=focus["revision"]:
            raise HTTPException(409,"该声检窗口属于旧接线版本")
        current=same_slot(conn,focus)
        if {x["code"] for x in current}!={x["code"] for x in captured["simultaneous"]}:
            raise HTTPException(409,"同期同频证据有新增，请重新判别")
        conn.execute(findings.insert().values(code=form.code,focus_window=focus["code"],category=rating["category"],
                    score=rating["score"],neighbors=rating["neighbors"],shared_points=rating["shared_points"],
                    reviewed_by=user["sub"],compute_token=form.token,
                    basis=codes,basis_detail=manifest))
        record(conn,user,f"finding:{form.code}:{rating['category']}")
        row=one(conn,findings,form.code)
        return present_finding(row,withdrawn_codes(conn))


def verification(code):
    with transaction() as conn:
        data=verification_in_conn(conn,code)
    available=False
    try:
        available=bool(broker.exists(f"compute:{data['compute_token']}"))
    except Exception:
        available=False
    data["credential_available"]=available
    data["token_present"]=available
    data["evidence"]=data.get("basis_detail")
    data["basis_manifest"]=data.get("basis_detail")
    # 同时提供嵌套 finding 视图，兼容不同核对接口结构。
    data["finding"]={key:value for key,value in data.items()
                     if key not in ("finding","samples","basis_samples")}
    return data
