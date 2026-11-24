from datetime import datetime, timezone

from fastapi import HTTPException

from core.audit import record
from core.db import transaction
from domain.catalog import impact_in_conn, latest, one, present_window
from domain.soundboard import points, windows
from domain.states import Patch


def capture(form,user):
    with transaction() as conn:
        point=one(conn,points,form.point,lock=True)
        purpose="reline" if point["patch"]==Patch.ISOLATED else "live"
        previous=latest(conn,point,purpose)
        if previous and form.slot<=previous["slot"]:
            raise HTTPException(409,"本接线版本的声检窗时刻须递增")
        conn.execute(windows.insert().values(**form.model_dump(),channel=point["channel"],
                     revision=point["revision"],purpose=purpose))
        record(conn,user,f"audio:{form.code}:{purpose}")
        return present_window(one(conn,windows,form.code))


def withdraw(form,user,code=None):
    target=code or (form.target() if form is not None else None)
    if not target:
        raise HTTPException(422,"请提供要撤回的样本编号")
    reason=(getattr(form,"reason",None) or getattr(form,"note",None) or None)
    with transaction() as conn:
        sample=one(conn,windows,target,lock=True)
        if not bool(sample["withdrawn"]):
            # 只打撤回标记，绝不删除 sound_windows 原行。
            conn.execute(windows.update().where(windows.c.code==target).values(
                withdrawn=True,withdrawn_by=user["sub"],
                withdrawn_at=datetime.now(timezone.utc),withdraw_reason=reason))
            record(conn,user,f"withdraw:{target}")
        result=present_window(one(conn,windows,target))
        impact=impact_in_conn(conn,target)
    return {
        **result,
        "sample": result,
        "sample_code": target,
        "impact": impact,
        "findings": impact["findings"],
        "affected_findings": impact["affected_findings"],
        "affected": impact["affected"],
        "affected_codes": impact["affected_codes"],
        "count": impact["count"],
        "unverifiable_findings": impact["unverifiable_findings"],
        "unverifiable_count": impact["unverifiable_count"],
    }
