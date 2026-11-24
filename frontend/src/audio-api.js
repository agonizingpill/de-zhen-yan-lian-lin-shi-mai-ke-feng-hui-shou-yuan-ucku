import {awaitCompute,request} from './api.js';

export const mixer = {
  patch:()=>request('/patch'), capture:body=>request('/audio',body), windows:()=>request('/audio'),
  baseline:()=>request('/audio/baseline'),
  withdraw:body=>request('/audio/withdraw',body),
  impact:code=>request('/feedback/impact?code='+encodeURIComponent(code)),
  verify:code=>request('/feedback/'+encodeURIComponent(code)+'/verify'),
  diagnosis:body=>request('/feedback/diagnose',body), wait:awaitCompute,
  save:body=>request('/feedback/save',body), findings:()=>request('/feedback'),
  isolate:body=>request('/patch/isolate',body), probe:(code,body)=>request('/patch/'+code+'/probe',body),
  restore:(code,body)=>request('/patch/'+code+'/restore',body),
};
