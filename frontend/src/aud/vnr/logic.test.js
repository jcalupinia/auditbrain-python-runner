import {describe,it,expect} from 'vitest';
import {applyTable} from './logic';
describe('VNR unión de fuentes',()=>{
 it('bloquea precios faltantes',()=>expect(()=>applyTable([{code:'A'},{code:'B'}],{name:'precios',rows:[['A','20']]},{code:'0',selling_price:'1'},'prices','p.csv')).toThrow('Faltan datos'));
 it('une por código, no por posición',()=>{const r=applyTable([{code:'B',source:'i'},{code:'A',source:'i'}],{name:'p',rows:[['A','10'],['B','30']]},{code:'0',selling_price:'1'},'prices','p.csv');expect(r[0].selling_price).toBe('30');expect(r[1].selling_price).toBe('10');});
 it('rechaza duplicados y mapeo faltante',()=>expect(()=>applyTable([],{rows:[['A'],['A']]},{code:0},'inventory','i')).toThrow());
});
