import {getToken} from '../../api.js';
const base=(import.meta.env.VITE_API_BASE??'https://auditbrain-python-runner.onrender.com').replace(/\/$/,'')+'/api/v1/aud/inventarios-vnr/';
async function call(project,path,options={}){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),90000);
 try{const response=await fetch(base+encodeURIComponent(project)+'/'+path,{...options,signal:controller.signal,headers:{Authorization:'Bearer '+getToken(),...options.headers}});
 if(!response.ok){let body;try{body=await response.json()}catch{}throw Error(typeof body?.detail==='string'?body.detail:'No se pudo completar la operación ('+response.status+').');}return response;
 }catch(e){if(e.name==='AbortError')throw Error('El procesamiento tardó demasiado. Revise el tamaño del archivo y vuelva a intentar.');throw e;}finally{clearTimeout(timer)}
}
export async function loadContext(project){return (await call(project,'context')).json()}
export async function extractFile(project,file){if(file.size>8*1024*1024)throw Error('Máximo 8 MB por archivo.');return (await call(project,'extract?filename='+encodeURIComponent(file.name),{method:'POST',body:file,headers:{'Content-Type':'application/octet-stream'}})).json()}
export async function processVnr(project,payload){return (await call(project,'process',{method:'POST',body:JSON.stringify(payload),headers:{'Content-Type':'application/json'}})).json()}
export async function downloadVnr(project,payload,format){const r=await call(project,'download?format='+format,{method:'POST',body:JSON.stringify(payload),headers:{'Content-Type':'application/json'}});saveBlob(await r.blob(),'AuditBrain_VNR.'+format)}
export function saveBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000)}
