from fastapi import APIRouter, Depends, HTTPException

from core.auth import actor, allow
from core.roles import REVIEW, WRITE
from domain import catalog, channel, diagnose, soundcheck
from domain.forms import (Capture, Diagnose, Isolate, RelineProbe, Restore,
                          SaveFinding, WithdrawSample)

patch=APIRouter(prefix="/patch")
audio=APIRouter(prefix="/audio")
feedback=APIRouter(prefix="/feedback")
samples=APIRouter(prefix="/samples")
routers=(patch,audio,feedback,samples)


@patch.get("")
def points(user=Depends(actor)):
    return catalog.patchboard()


@audio.get("")
def windows(purpose:str | None=None,user=Depends(actor)):
    # 不带参数时保持原契约：返回非基线窗口；显式 purpose 时按其过滤。
    if purpose is None:
        return catalog.audio()
    return catalog.samples_view(purpose)


@audio.get("/baseline")
def baseline_windows(user=Depends(actor)):
    return catalog.baseline_view()


@audio.get("/withdrawals")
def audio_withdrawals(user=Depends(actor)):
    return catalog.withdrawals_view()


@audio.get("/all")
def all_windows(user=Depends(actor)):
    return catalog.samples_view("all")


@audio.post("",status_code=201)
def capture(form:Capture,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.capture(form,user)


@audio.post("/withdraw")
@audio.post("/revoke")
@audio.post("/recall")
def withdraw_sample(form:WithdrawSample,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(form,user)


@audio.post("/{code}/withdraw")
@audio.post("/{code}/revoke")
@audio.post("/{code}/recall")
def withdraw_window(code:str,form:WithdrawSample | None=None,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(form or WithdrawSample(),user,code=code)


@audio.delete("/{code}")
def delete_window_soft(code:str,form:WithdrawSample | None=None,user=Depends(actor)):
    # 撤回=软删除：保留原样本行，只打撤回标记。
    allow(user,WRITE)
    return soundcheck.withdraw(form or WithdrawSample(),user,code=code)


@audio.get("/{code}/impact")
def window_impact(code:str,user=Depends(actor)):
    return catalog.impact_view(code)


def _flag(value):
    if value is None:
        return None
    return str(value).strip().lower() in ("1","true","yes","y","on")


_BOOL_TOKENS={"1","0","true","false","yes","no","y","n","on","off",""}


@feedback.get("")
def findings(sample:str | None=None,code:str | None=None,window:str | None=None,
             basis:str | None=None,sample_code:str | None=None,
             withdrawn:str | None=None,affected:str | None=None,
             verifiable:str | None=None,unverifiable:str | None=None,
             user=Depends(actor)):
    items=catalog.diagnosis()
    target=sample or code or window or basis or sample_code
    flag_withdrawn=_flag(withdrawn) if withdrawn is not None else None
    flag_affected=_flag(affected) if affected is not None else None
    # withdrawn/affected 既可能是开关，也可能直接传样本编号。
    for value in (withdrawn,affected):
        token=str(value or "").strip().lower()
        if value and token not in _BOOL_TOKENS:
            target=target or value
    if target:
        items=[x for x in items
               if target in (x.get("used_samples") or [])
               or x.get("code")==target or x.get("focus_window")==target]
    if flag_withdrawn or flag_affected:
        items=[x for x in items if x.get("withdrawn_refs")]
    if verifiable is not None:
        wanted=_flag(verifiable)
        items=[x for x in items if bool(x.get("verifiable")) is bool(wanted)]
    if unverifiable is not None:
        wanted=_flag(unverifiable)
        items=[x for x in items if (not x.get("verifiable")) is bool(wanted)]
    return items


# 注意：/feedback/impact 等集合路径必须先于 /feedback/{code} 注册。
@feedback.get("/impact")
def findings_impact(code:str | None=None,sample:str | None=None,window:str | None=None,
                    user=Depends(actor)):
    target=code or sample or window
    if not target:
        raise HTTPException(422,"请提供要查询的样本编号")
    return catalog.impact_view(target)


@feedback.get("/affected")
def findings_affected(code:str | None=None,sample:str | None=None,window:str | None=None,
                      user=Depends(actor)):
    return findings_impact(code,sample,window,user)


@feedback.get("/withdrawn")
def findings_withdrawn(user=Depends(actor)):
    return [x for x in catalog.diagnosis() if x.get("withdrawn_refs")]


@feedback.post("/withdraw")
@feedback.post("/revoke")
@feedback.post("/recall")
def feedback_withdraw(form:WithdrawSample,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(form,user)


@feedback.post("/diagnose",status_code=202)
def probe(form:Diagnose,user=Depends(actor)):
    allow(user,WRITE)
    return diagnose.diagnose(form,user)


@feedback.post("/save",status_code=201)
def save(form:SaveFinding,user=Depends(actor)):
    allow(user,WRITE)
    return diagnose.save(form,user)


@feedback.get("/{code}/verify")
def verify_finding(code:str,user=Depends(actor)):
    return diagnose.verification(code)


@feedback.get("/verify/{code}")
def verify_finding_alt(code:str,user=Depends(actor)):
    return diagnose.verification(code)


@feedback.get("/{code}")
def finding_detail(code:str,user=Depends(actor)):
    return diagnose.verification(code)


@samples.get("")
def sample_list(purpose:str | None=None,user=Depends(actor)):
    return catalog.samples_view(purpose)


@samples.get("/baseline")
def sample_baseline(user=Depends(actor)):
    return catalog.baseline_view()


@samples.get("/withdrawn")
def sample_withdrawn(user=Depends(actor)):
    return catalog.withdrawals_view()


@samples.post("/withdraw")
@samples.post("/revoke")
@samples.post("/recall")
def samples_withdraw(form:WithdrawSample,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(form,user)


@samples.post("/{code}/withdraw")
@samples.post("/{code}/revoke")
@samples.post("/{code}/recall")
def sample_withdraw_code(code:str,form:WithdrawSample | None=None,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(form or WithdrawSample(),user,code=code)


@samples.delete("/{code}")
def sample_delete_soft(code:str,user=Depends(actor)):
    allow(user,WRITE)
    return soundcheck.withdraw(WithdrawSample(),user,code=code)


@samples.get("/{code}/impact")
def sample_impact(code:str,user=Depends(actor)):
    return catalog.impact_view(code)


@samples.get("/{code}")
def sample_detail(code:str,user=Depends(actor)):
    return catalog.sample_view(code)


@patch.post("/isolate",status_code=201)
def isolate(form:Isolate,user=Depends(actor)):
    allow(user,REVIEW)
    return channel.isolate(form,user)


@patch.post("/{code}/probe",status_code=202)
def verify(code:str,form:RelineProbe,user=Depends(actor)):
    allow(user,WRITE)
    return channel.probe(code,form,user)


@patch.post("/{code}/restore")
def restore(code:str,form:Restore,user=Depends(actor)):
    allow(user,REVIEW)
    return channel.restore(code,form,user)
