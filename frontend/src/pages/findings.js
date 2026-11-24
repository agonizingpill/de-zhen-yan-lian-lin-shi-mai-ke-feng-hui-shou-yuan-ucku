import {el} from '../dom.js';
import {mixer} from '../audio-api.js';
import {desk,labels,sampleState} from '../audio-state.js';
import {choices,field,run,write} from '../audio-form.js';
import {status,titleBlock} from '../widgets.js';
import {basisBlock,diagnosis,metrics,verifiabilityTag,verifyReport,withdrawnRefTags} from '../components/samples.js';
import {badge} from '../components/badge.js';

export async function findings(root,role) {
  const edit=el('section',{class:'action'});
  const box=el('section',{class:'ledger'});
  const govern=el('section',{class:'ledger govern'});
  let impactBox=null;
  let impactCode=null;

  function findingDetail(item) {
    const report=el('div',{class:'verify-slot'});
    const button=el('button',{type:'button',class:'quiet verify-btn'},'核对原分与用样依据');
    button.addEventListener('click',async()=>{
      button.disabled=true;
      report.replaceChildren(status('正在读取签存结论…'));
      try {
        report.replaceChildren(verifyReport(await mixer.verify(item.code)));
      } catch(error) {
        report.replaceChildren(status(error.message,'error'));
      } finally {button.disabled=false;}
    });
    return el('details',{class:'clip finding'+(item.affected?' is-affected':'')
        +(item.verifiable===false?' is-unverifiable':''),...(item.affected?{open:''}:{})},
      el('summary',{},el('code',{},item.code+' · '+item.focus_window),
        verifiabilityTag(item),item.affected?withdrawnRefTags(item):null),
      diagnosis(item),basisBlock(item),
      el('div',{class:'verify-actions'},button),report);
  }

  function renderBox(items) {
    box.replaceChildren(el('h2',{},'邻域局部密度与同频检查'),
      ...items.map(findingDetail));
  }

  function renderEdit(clips,message) {
    const active=clips.filter(clip=>clip.purpose==='live');
    const result=el('div',{class:'live-review'});
    edit.replaceChildren(...[el('h2',{},'选择试听窗'),
      message?status(message,'ok'):null].filter(Boolean));
    if (!write(role)) {edit.append(status('只读账号可展开已签发现、核对用样并查询受影响结论。'));return;}
    edit.append(run('diagnose',[
      choices('window','窗口',active.map(x=>[x.code,x.code+' / '+x.point]),desk.window),
    ],'并行证据诊断',async values=>{
      const focus=active.find(item=>item.code===values.get('window'));
      const job=await mixer.diagnosis({window:focus.code});
      const report=await mixer.wait(job.token,item=>{
        if(item.status==='queued') result.replaceChildren(status('邻域密度计算中'));
      });
      if(report.status!=='ready') throw new Error(report.detail);
      result.replaceChildren(el('h3',{class:'mono'},focus.code),
        metrics(focus),
        diagnosis(report.result),
        el('p',{},'参考 '+report.result.reference_windows+' 个窗，正常下限 '+report.result.threshold),
        run('save-finding',[field('code','发现编号',{placeholder:'FD-1124-HUB'})],'签发现',async data=>{
          const item=await mixer.save({code:data.get('code'),token:job.token});
          desk.finding=item.code;
          impactCode=(item.withdrawn_refs&&item.withdrawn_refs[0])||impactCode;
          await load(item.code+' 已签入。'+(item.withdrawn_refs.length
            ?' 该结论使用了已撤回样本 '+item.withdrawn_refs.join(' · ')+'，已在结论上标出。':''),
            {impact:impactCode});
        }));
    }),result);
  }

  function renderImpact(imp) {
    const rows=imp.affected_findings||imp.findings||[];
    return el('div',{class:'impact-result','data-code':imp.code},
      el('h3',{},'受影响的结论 · '+imp.code),
      imp.withdrawn?badge(sampleState,'withdrawn'):el('span',{class:'signal-tag','data-state':'active'},'样本未撤回'),
      rows.length
        ? el('ul',{class:'impact-list'},...rows.map(f=>el('li',{},
            el('code',{},f.code),' · '+(labels[f.category]||f.category),
            ' · LOF '+Number(f.score).toFixed(4),
            (f.withdrawn_refs||[]).length
              ?el('span',{class:'impact-refs'},' 命中撤回用样 '+f.withdrawn_refs.join(' · ')):null)))
        : status('没有已签结论以该样本为用样依据。'),
      imp.affected_codes&&imp.affected_codes.length
        ? el('p',{class:'mono impact-codes','aria-label':'受影响结论编号'},imp.affected_codes.join(' · ')):null,
      imp.unverifiable_count
        ? status('另有 '+imp.unverifiable_count+' 条旧记录缺少用样依据，无法核实是否受影响。'):null);
  }

  async function renderImpactInto(code) {
    if(!impactBox || !code) return;
    impactBox.replaceChildren(status('正在查询 '+code+' 影响的结论…'));
    try {
      const imp=await mixer.impact(code);
      impactCode=code;
      impactBox.replaceChildren(renderImpact(imp));
    } catch(error) {
      impactBox.replaceChildren(status(error.message,'error'));
    }
  }

  function renderGovern(baseline,message,errorMessage) {
    impactBox=el('div',{class:'impact-box'});
    const impactSelect=el('select',{name:'impact_code','aria-label':'影响查询样本'},
      el('option',{value:''},'选择样本编号'),
      ...baseline.map(x=>el('option',{value:x.code,...(impactCode===x.code?{selected:''}:{})},
        x.code+(x.withdrawn?'（已撤回）':''))));
    const query=el('form',{class:'impact-query'},
      el('label',{},el('span',{},'影响查询样本'),impactSelect),
      el('button',{type:'submit'},'查询受影响结论'));
    query.addEventListener('submit',event=>{
      event.preventDefault();
      const code=impactSelect.value;
      if(code) renderImpactInto(code);
    });

    govern.replaceChildren(...[
      el('h2',{},'基线样本撤回与影响核查'),
      el('p',{class:'intro'},'演练后发现试音啸叫混入正常基线时在此撤回。撤回只做标记、不删除原样本；'
        +'撤回后新诊断和备用路复测都不再采用它，已取样的计算按原快照照常完成，结论会标出用过的撤回样本。'),
      message?status(message,'ok'):null,
      errorMessage?status(errorMessage,'error'):null].filter(Boolean));

    if(write(role)) {
      govern.append(run('withdraw-sample',[
        el('label',{},el('span',{},'样本编号'),
          el('input',{name:'code',list:'withdraw-code-options',required:'',
            placeholder:'REF-01','aria-label':'样本编号'})),
        el('datalist',{id:'withdraw-code-options'},baseline.map(x=>el('option',{value:x.code}))),
        field('reason','撤回原因（可选）',{maxlength:'200',placeholder:'如：试音啸叫混入正常基线'}),
      ],'撤回样本',async values=>{
        const code=String(values.get('code')||'').trim();
        const reason=String(values.get('reason')||'').trim();
        const out=await mixer.withdraw({code,reason:reason||null});
        impactCode=code;
        await load(code+' 已撤回，原样本保留未删；'+out.count+' 条已签结论以它为用样依据。',{impact:code,govern:true});
      }));
    } else {
      govern.append(status('只读账号可查看基线样本、撤回状态并查询受影响结论。'));
    }

    govern.append(el('h3',{},'基线样本（'+baseline.length+'）'),
      el('div',{class:'baseline-list'},
        el('div',{class:'baseline-row head'},el('span',{},'编号'),el('span',{},'刻度 / 频率'),
          el('span',{},'状态与原因'),el('span',{},'操作'))),
      ...baseline.map(x=>{
        const state=el('span',{class:'baseline-state'},
          badge(sampleState,x.withdrawn?'withdrawn':'active'),
          x.withdraw_reason?el('small',{},x.withdraw_reason):null);
        let action=el('span',{});
        if(write(role)&&!x.withdrawn) {
          const button=el('button',{type:'button',class:'quiet row-withdraw','aria-label':'撤回 '+x.code},'撤回此样本');
          button.addEventListener('click',async()=>{
            button.disabled=true;
            try {
              const out=await mixer.withdraw({code:x.code});
              impactCode=x.code;
              await load(x.code+' 已撤回，原样本保留未删；'+out.count+' 条已签结论以它为用样依据。',{impact:x.code,govern:true});
            } catch(error) {
              await load('',{error:error.message,govern:true});
            }
          });
          action=el('span',{class:'row-action'},button);
        } else if(x.withdrawn_by) {
          action=el('small',{class:'mono'},x.withdrawn_by);
        }
        return el('div',{class:'baseline-row'+(x.withdrawn?' is-withdrawn':'')},
          el('code',{},x.code),
          el('span',{class:'mono'},x.slot+' / '+x.frequency+' Hz'),
          state,action);
      }));

    govern.append(el('h3',{},'影响核查'),query,impactBox);
  }

  async function load(message,opts={}) {
    if(Object.prototype.hasOwnProperty.call(opts,'impact')) impactCode=opts.impact;
    const [clips,items,baseline]=await Promise.all([
      mixer.windows(),mixer.findings(),mixer.baseline()]);
    renderBox(items);
    renderEdit(clips,opts.govern?null:message);
    renderGovern(baseline,opts.govern?message:null,opts.error);
    if(impactCode) renderImpactInto(impactCode);
  }

  root.replaceChildren(
    titleBlock('安澜 · 邻域诊断','回授源、同频证据与样本撤回',
      '异常先核对同一时间窗的主峰。混入基线的试音啸叫可撤回并追踪受影响结论；签存的用样依据在计算凭证过期后仍可核对。'),
    govern,
    el('div',{class:'mix invert'},edit,box));
  await load();
}
