import {el} from '../dom.js';
import {feature,labels,purpose,sampleState,verifyState} from '../audio-state.js';
import {badge} from './badge.js';

export function metrics(clip) {
  return el('div',{class:'sampler','aria-label':'样本声检特征'},Object.entries(feature).flatMap(([key,label])=>
    [el('span',{},label),el('meter',{min:'0',max:'1',value:clip[key],'aria-label':label}),
      el('code',{},Number(clip[key]).toFixed(2))]));
}

export function withdrawnTag(clip) {
  if (!clip || !clip.withdrawn) return null;
  return el('span',{class:'signal-tag is-withdrawn','data-state':'withdrawn'},sampleState.withdrawn);
}

export function sample(clip) {
  return el('details',{class:'clip'+(clip.withdrawn?' is-withdrawn':'')},
    el('summary',{},clip.code+' · '+clip.point+' · '+clip.slot+' / '+clip.frequency+' Hz · '
      +(purpose[clip.purpose]||clip.purpose),withdrawnTag(clip)),
    clip.withdraw_reason?el('p',{class:'withdraw-reason'},'撤回原因：'+clip.withdraw_reason):null,
    metrics(clip));
}

export function diagnosis(item) {
  return el('div',{class:'note'},badge(labels,item.category),el('p',{class:'mono'},
    'LOF '+Number(item.score).toFixed(4)+' · 邻居 '+item.neighbors),
    el('p',{},item.shared_points.length ? '同期相符麦位 '+item.shared_points.join(' · ') : '没有同期相符的麦位。'));
}

export function verifiabilityTag(item) {
  if (item.verifiable === false) {
    return el('span',{class:'signal-tag is-unverifiable','data-state':'unverifiable'},verifyState.unverifiable);
  }
  return el('span',{class:'signal-tag is-verified','data-state':'verified'},verifyState.verified);
}

export function withdrawnRefTags(item) {
  const refs=item.withdrawn_refs||[];
  if (!refs.length) return null;
  return el('span',{class:'signal-tag is-withdrawn','data-state':'withdrawn',
    title:'该结论送检快照使用了已撤回样本，分数按原快照保留'},'使用已撤回样本 '+refs.join(' · '));
}

export function basisBlock(item) {
  if (item.verifiable === false) {
    return el('p',{class:'basis missing'},'无法核实：旧记录缺少用样依据，未记录当时采用的基线样本。');
  }
  const codes=item.basis_codes||item.basis||[];
  const refs=item.withdrawn_refs||[];
  return el('div',{class:'basis'},
    el('p',{},'用样依据：签存 '+codes.length+' 个基线窗编号；计算凭证过期后仍可核对原分数与用样。'),
    el('details',{class:'basis-codes'},el('summary',{},'查看基线样本编号'),
      el('code',{class:'mono'},codes.join(' · '))),
    refs.length
      ? el('p',{class:'status error'},'该结论使用了已撤回样本：'+refs.join(' · ')
          +'。结论按送检时快照照常算完，撤回不删除原样本。')
      : null);
}

export function verifyReport(v) {
  if (v.verifiable === false) {
    return el('div',{class:'verify-report unverifiable'},
      el('p',{class:'status error'},v.message||'旧记录缺少用样依据，无法核实。'),
      el('p',{class:'mono'},'原分数 LOF '+Number(v.score).toFixed(4)+'（分数仍在，但用样依据缺失）'));
  }
  const samples=v.basis_samples||v.samples||[];
  return el('div',{class:'verify-report'},
    el('p',{class:'status ok'},v.message||'已核对签存的原分数与用样依据。'),
    el('p',{class:'mono'},'原分数 LOF '+Number(v.original_score??v.score).toFixed(4)
      +' · 基线 '+((v.basis_codes||v.basis||[]).length)+' 窗'),
    el('p',{},v.credential_available===false
      ? '计算凭证已过期或不存在；以下核对完全依据签存结论与保留样本。'
      : '计算凭证仍在 Redis 中，签存记录可独立核对。'),
    (v.withdrawn_refs||[]).length
      ? el('p',{class:'status error'},'其中已撤回：'+v.withdrawn_refs.join(' · '))
      : el('p',{},'用样均未撤回。'),
    samples.length ? el('details',{class:'basis-codes'},el('summary',{},'核对保留的原样本（'+samples.length+'）'),
      ...samples.map(s=>el('p',{class:'mono sample-check'+(s.withdrawn?' is-withdrawn':'')},
        (s.missing?'[原行缺失] ':s.code+' · '+s.point+' · slot '+s.slot+' · '),
        s.withdrawn?'已撤回':'采用中'))) : null);
}
