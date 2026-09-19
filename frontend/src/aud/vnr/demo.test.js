import {describe,it,expect} from 'vitest';
import ExcelJS from 'exceljs';
import {File as NodeFile} from 'node:buffer';
import {DEMO,exampleFile,demoContext,demoPolicy} from './demo.js';
import {SLOTS,applyTable} from './logic.js';
if(!globalThis.File)globalThis.File=NodeFile;
describe('VNR demo importable',()=>{
 it('reimports all generated Excel sources with the actual column mapping',async()=>{
  let rows=[];
  for(const [slot,,keys] of SLOTS.filter(s=>s[2].length)){
   const file=await exampleFile(slot);const wb=new ExcelJS.Workbook();await wb.xlsx.load(await file.arrayBuffer());const ws=wb.worksheets[0];
   const table={name:ws.name,headers:ws.getRow(1).values.slice(1),rows:[]};for(let i=2;i<=ws.rowCount;i++)table.rows.push(ws.getRow(i).values.slice(1));
   rows=applyTable(rows,table,Object.fromEntries(keys.map(k=>[k,table.headers.indexOf(k)])),slot,file.name);
  }
  expect(rows).toHaveLength(3);expect(rows[0].selling_price).toBe('18');expect(rows[1].recorded_impairment).toBe('40');expect(rows[2].selling_cost).toBe('2');
  expect(rows.every(r=>r.source.includes('inventory')&&r.source.includes('prices')&&r.source.includes('expenses'))).toBe(true);
 });
 it('blank templates contain only headers and review is never pre-approved',async()=>{
  const file=await exampleFile('inventory',true);const wb=new ExcelJS.Workbook();await wb.xlsx.load(await file.arrayBuffer());expect(wb.worksheets[0].rowCount).toBe(1);
  for(const framework of ['full','sme']){expect(demoPolicy(framework).reviewed).toBe(false);expect(demoPolicy(framework).evidence_reviewed).toBe(false);expect(demoContext(framework).reuse_scope).toBe('one');}
  expect((await exampleFile('policy')).name).toMatch(/DEMO.txt$/);expect(DEMO.expected.adjustment).toBe('45.00');
 });
});
